from datetime import datetime
from shutil import make_archive
from subprocess import run
from shutil import rmtree
from re import sub
from pathlib import Path
from mcstatus import BedrockServer as _BedrockServerStatus
import requests
from zipfile import ZipFile
from io import BytesIO
from fake_useragent import UserAgent


class BedrockServer:

    # Server name length limits
    MIN_NAME_LEN = 4
    MAX_NAME_LEN = 32

    # URL and headers for update
    _UPDATE_LINKS_URL = "https://net-secondary.web.minecraft-services.net/api/v1.0/download/links"
    _USER_AGENT = {
        "User-Agent": UserAgent(platforms=["desktop"]).random
    }

    # Server files and directories to normally exclude from updating and replacing
    _UPDATER_EXCLUDE_FILES = [
        "allowlist.json",
        "packetlimitconfig.json",
        "permissions.json",
        "profanity_filter.wlist",
        "server.properties"
    ]
    _UPDATER_EXCLUDE_DIRS = [
        "config"
    ]

    # File paths and names
    _DIR = Path.home().joinpath("BSW")
    _BEDROCK_SERVER_PROGRAM_NAME = "bedrock_server"
    _BEDROCK_SERVER_PROPERTIES_FILE_NAME = "server.properties"
    _DIR.mkdir(parents=True, exist_ok=True)

    # Empty dictionary to load server.properties into when ready
    _SERVER_PROPERTIES: dict[str, str] = {}

    # Constructor blocker to allow methods to validate server_name differently
    _CONSTRUCTOR_BLOCKER = object()

    def __init__(self, server_name: str, token: object) -> None:
        """
        :param server_name: Case-insensitive name for the server.
            Must be alphanumeric and between MIN_NAME_LENGTH and MAX_NAME_LENGTH characters long.
        :raises ValueError: If the server name is invalid.
        """
        if token is not self._CONSTRUCTOR_BLOCKER:
            raise RuntimeError("Use BedrockServer.create or BedrockServer.load to get a BedrockServer instance.")
        self.server_name = server_name.lower()

    @classmethod
    def create(cls, server_name: str) -> "BedrockServer | str":
        if not BedrockServer._validate_name(server_name):
            return "Server name is invalid."
        elif server_name in cls.list_servers():
            return "Server already exists."
        new_server = cls(server_name, cls._CONSTRUCTOR_BLOCKER)
        new_server._download_and_update()
        return new_server

    @classmethod
    def load(cls, server_name: str) -> "BedrockServer | str":
        if not server_name in cls.list_servers():
            return "Server does not exist."
        return cls(server_name, cls._CONSTRUCTOR_BLOCKER)

    @property
    def _folder(self) -> Path:
        return self._DIR.joinpath(self.server_name)

    @property
    def server_subfolder(self) -> Path:
        return self._folder.joinpath("server")

    @property
    def backups_subfolder(self) -> Path:
        return self._folder.joinpath("backups")

    @property
    def _executable_path(self) -> Path:
        return self.server_subfolder.joinpath(self._BEDROCK_SERVER_PROGRAM_NAME)

    @staticmethod
    def check_screen() -> bool:
        return len(run(["which", "screen"], capture_output=True).stdout) > 0

    @staticmethod
    def _active_screen_sessions_display() -> str:
        return run(["screen", "-ls"], capture_output=True, text=True).stdout

    def is_running(self) -> bool:
        return self._session_name in self._active_screen_sessions_display()

    @staticmethod
    def _validate_name(server_name: str) -> bool:
        return server_name.isalnum() and BedrockServer.MIN_NAME_LEN <= len(server_name) <= BedrockServer.MAX_NAME_LEN

    @property
    def _session_name(self) -> str:
        return f"bsw-{self.server_name}"

    @property
    def attach_session_command(self) -> str:
        return f"screen -r {self._session_name}"

    def start(self) -> None:
        try:
            self._download()
        except RuntimeError:
            raise RuntimeError("Server is already running.")
        for server_name in self.list_servers():
            if server_name == self.server_name:
                continue
            other_server = self.__class__(server_name, self._CONSTRUCTOR_BLOCKER)
            other_server_ports = (other_server.get_port_number(), other_server.get_port_number(ipv6=True))
            if self.get_port_number() in other_server_ports or self.get_port_number(ipv6=True) in other_server_ports:
                raise OSError("Server ports conflict with another server.")
        if self._get_server_property("enable-lan-visibility") != "false":
            raise OSError("Server cannot be set to enable LAN visibility as it may cause port conflicts.")
        run(["screen", "-dmS", self._session_name, "bash", str(self._starter_path)])

    def stop(self, force_stop: bool = False) -> None:
        if not self.is_running():
            return
        if not force_stop and self.get_player_count():
            raise RuntimeError("Cannot stop server while players are online without force stopping.")
        self._execute("stop")

    def backup(self, enforce_cooldown_minutes: int, backup_limit: int, force_backup: bool = False) -> None:
        last_backup = self._recent_backup_age_minutes()
        if enforce_cooldown_minutes and last_backup is not None and not force_backup:
            if last_backup < enforce_cooldown_minutes:
                raise FileExistsError("Previous backup is too recent.")
        stop_and_restart = self.is_running()
        if stop_and_restart:
            try:
                self.stop(force_stop=force_backup)
            except RuntimeError:
                raise RuntimeError("Cannot backup server while players are online without force stopping.")
        self._do_backup()
        if stop_and_restart:
            self.start()
        self._limit_backups(backup_limit)

    def message(self, message: str) -> None:
        if not self.is_running():
            return
        message = sub(r"&(?!\s)", "§", message)
        self._execute(f"say {message}")

    def purge(self) -> None:
        if self.is_running():
            return
        rmtree(self._folder, ignore_errors=True)

    def _execute(self, command: str) -> None:
        run(["screen", "-S", self._session_name, "-p", "0", "-X", "stuff", f"{command}\\n"])

    def _download(self) -> None:
        if self.is_running():
            raise RuntimeError("Cannot download server while it is running.")
        self._download_and_update()

    def get_player_count(self) -> int:
        return _BedrockServerStatus("127.0.0.1", self.get_port_number()).status().players.online

    @classmethod
    def list_online_servers(cls) -> list[str]:
        active_sessions_display = BedrockServer._active_screen_sessions_display()
        return [server for server in cls.list_servers() if server in active_sessions_display]

    @staticmethod
    def _get_download_url() -> str:
        try:
            response = requests.get(BedrockServer._UPDATE_LINKS_URL, headers=BedrockServer._USER_AGENT, timeout=10)
            response.raise_for_status()
            urls_data: dict = response.json()
        except requests.Timeout:
            raise TimeoutError("Request for download links timed out.")
        except requests.HTTPError:
            raise ConnectionError("Request for download links unsuccessful.")
        urls_data: list[dict] = urls_data["result"]["links"]
        download_url: str | None = None
        for url_data in urls_data:
            if url_data["downloadType"] == "serverBedrockLinux":
                download_url = url_data["downloadUrl"]
        if download_url is None:
            raise KeyError("No download URL for Linux server found.")
        return download_url

    def _download_and_update(self) -> None:
        download_url = self._get_download_url()
        overwrite_all = False if self._executable_and_properties_exist() else True
        if self._last_update_url == download_url and not overwrite_all:
            return
        try:
            server_zip_response = requests.get(download_url, headers=self._USER_AGENT, timeout=30)
            server_zip_response.raise_for_status()
            server_zip_data = server_zip_response.content
        except requests.Timeout:
            raise TimeoutError("Request for server download timed out.")
        except requests.HTTPError:
            raise ConnectionError("Request for server download unsuccessful.")
        self._last_update_url = download_url
        with ZipFile(BytesIO(server_zip_data)) as server_zip:
            if overwrite_all:
                members = server_zip.namelist()
            else:
                members = [file for file in server_zip.namelist() if file not in self._UPDATER_EXCLUDE_FILES]
                members = [file for file in members for folder in self._UPDATER_EXCLUDE_DIRS if not file.startswith(folder)]
            server_zip.extractall(self.server_subfolder, members=members)
        with open(self._starter_path, "w") as starter_file:
            starter_file.writelines([
                "#!/usr/bin/env bash\n",
                f"cd \"{self.server_subfolder}\"\n",
                "LD_LIBRARY_PATH=. ./bedrock_server"
            ])
        run(["chmod", "+x", self._executable_path], check=True)
        run(["chmod", "+x", self._starter_path], check=True)

    def _get_server_property(self, key: str, default: str | None = None) -> str | None:
        self._load_server_properties()
        return self._SERVER_PROPERTIES.get(key, default)

    def get_port_number(self, ipv6: bool = False) -> int:
        port = self._get_server_property("server-port" if not ipv6 else "server-portv6")
        if port is None:
            raise KeyError("Server port not found in server.properties file.")
        try:
            port = int(port)
        except TypeError:
            raise TypeError("Server port in server.properties is not an integer.")
        if port < 1024 or port > 65535:
            raise ValueError("Server port value in server.properties is out of range (too high or low).")
        return port

    def list_backups(self) -> list[str]:
        backup_directory = Path(self.backups_subfolder)
        backup_directory.mkdir(parents=True, exist_ok=True)
        existing_backups = list(backup_directory.glob("*.zip"))
        return [str(backup.relative_to(backup_directory)) for backup in existing_backups]

    def _limit_backups(self, limit: int) -> None:
        backups = self.list_backups()
        if len(backups) <= limit:
            return
        backups.sort(reverse=True)
        for backup in backups[limit:]:
            self.backups_subfolder.joinpath(backup).unlink()

    def _recent_backup_age_minutes(self) -> int | None:
        backups = self.list_backups()
        current_time = datetime.now()
        if not len(backups):
            return None
        backups.sort()
        while True:
            most_recent_backup = backups[-1].replace(".zip", "")
            backups = backups[:-1]
            if not len(backups):
                break
            try:
                most_recent_backup_date = datetime.strptime(most_recent_backup, "%Y-%m-%d_%H-%M-%S")
            except ValueError:
                continue
            return max(1, int(round((current_time - most_recent_backup_date).total_seconds() /  60)))

    def _do_backup(self) -> None:
        backup_name = f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
        backup_path = self.backups_subfolder.joinpath(backup_name)
        Path(self.backups_subfolder).mkdir(parents=True, exist_ok=True)
        make_archive(str(backup_path), "zip", self.server_subfolder)

    @classmethod
    def list_servers(cls) -> list[str]:
        return [server.name for server in cls._DIR.iterdir() if cls(server.name, cls._CONSTRUCTOR_BLOCKER)._executable_and_properties_exist()]

    def _load_server_properties(self) -> None:
        with open(self.server_subfolder.joinpath(self._BEDROCK_SERVER_PROPERTIES_FILE_NAME), "r") as file:
            for line in file:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                key, value = line.split("=", 1)
                self._SERVER_PROPERTIES[key] = value.strip()

    def _executable_and_properties_exist(self) -> bool:
        starter_exists = self._starter_path.is_file()
        executable_exists = self._executable_path.is_file()
        properties_exists = self.server_subfolder.joinpath(self._BEDROCK_SERVER_PROPERTIES_FILE_NAME).is_file()
        return starter_exists and executable_exists and properties_exists

    @property
    def _starter_path(self) -> Path:
        return self.server_subfolder.joinpath("starter.sh")

    @property
    def _last_update_url_file_path(self) -> Path:
        return self._folder.joinpath("last_update_url.txt")

    @property
    def _last_update_url(self) -> str:
        try:
            with open(self._last_update_url_file_path, "r") as file:
                return file.read()
        except FileNotFoundError:
            return ""

    @_last_update_url.setter
    def _last_update_url(self, url: str) -> None:
        self._last_update_url_file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._last_update_url_file_path, "w") as file:
            file.write(url)
