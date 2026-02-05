from ._system import SystemUtilities
from subprocess import run
from shutil import rmtree
from re import sub
from mcstatus import BedrockServer as _BedrockServerStatus
import requests
from zipfile import ZipFile
from io import BytesIO
from fake_useragent import UserAgent


class BedrockServer(SystemUtilities):

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

    def __init__(self, server_name: str) -> None:
        """
        :param server_name: Case-insensitive name for the server.
            Must be alphanumeric and between MIN_NAME_LENGTH and MAX_NAME_LENGTH characters long.
        :raises ValueError: If the server name is invalid.
        """
        server_name = server_name.lower()
        if not BedrockServer.validate_name(server_name):
            raise ValueError(f"Server name must be alphanumeric and {self.MIN_NAME_LEN}-{self.MAX_NAME_LEN} characters long.")
        SystemUtilities.__init__(self, server_name)

    @staticmethod
    def check_screen() -> bool:
        return len(run(["which", "screen"], capture_output=True).stdout) > 0

    @staticmethod
    def _active_screen_sessions_display() -> str:
        return run(["screen", "-ls"], capture_output=True, text=True).stdout

    def _check_running(self) -> bool:
        return self._session_name in self._active_screen_sessions_display()

    @staticmethod
    def validate_name(server_name: str) -> bool:
        return server_name.isalnum() and BedrockServer.MIN_NAME_LEN <= len(server_name) <= BedrockServer.MAX_NAME_LEN

    @property
    def _session_name(self) -> str:
        return f"bsw-{self.server_name}"

    @property
    def attach_session_command(self) -> str:
        return f"screen -r {self._session_name}"

    def new(self) -> None:
        if self.server_name in self.list_servers():
            raise FileExistsError("Server already exists.")
        self.download_and_update()

    def start(self) -> None:
        if self.server_name not in self.list_servers():
            raise FileNotFoundError("Server does not exist.")
        try:
            self._download()
        except RuntimeError:
            raise RuntimeError("Server is already running.")
        for server_name in self.list_servers():
            if server_name == self.server_name:
                continue
            other_server = SystemUtilities(server_name)
            other_server_ports = (other_server.port_number, other_server.port_number_ipv6)
            if self.port_number in other_server_ports or self.port_number_ipv6 in other_server_ports:
                raise OSError("Server ports conflict with another server.")
        if self.lan_visibility:
            raise OSError("Server cannot be set to enable LAN visibility as it may cause port conflicts.")
        run(["screen", "-dmS", self._session_name, "bash", str(self.starter_path)])

    def stop(self, force_stop: bool = False) -> None:
        if not self._check_running():
            return
        if not force_stop and self.get_player_count():
            raise RuntimeError("Cannot stop server while players are online without force stopping.")
        self._execute("stop")

    def backup(self, enforce_cooldown_minutes: int, backup_limit: int, force_backup: bool = False) -> None:
        last_backup = self.recent_backup_age_minutes()
        if enforce_cooldown_minutes and last_backup is not None and not force_backup:
            if last_backup < enforce_cooldown_minutes:
                raise FileExistsError("Previous backup is too recent.")
        stop_and_restart = self._check_running()
        if stop_and_restart:
            try:
                self.stop(force_stop=force_backup)
            except RuntimeError:
                raise RuntimeError("Cannot backup server while players are online without force stopping.")
        self.do_backup()
        if stop_and_restart:
            self.start()
        self.limit_backups(backup_limit)

    def message(self, message: str) -> None:
        if not self._check_running():
            raise RuntimeError("Cannot send message while server is not running.")
        message = sub(r"&(?!\s)", "§", message)
        self._execute(f"say {message}")

    def purge(self) -> None:
        if self._check_running():
            raise RuntimeError("Cannot purge server while it is running.")
        rmtree(self.folder, ignore_errors=True)

    def _execute(self, command: str) -> None:
        run(["screen", "-S", self._session_name, "-p", "0", "-X", "stuff", f"{command}\\n"])

    def _download(self) -> None:
        if self._check_running():
            raise RuntimeError("Cannot download server while it is running.")
        self.download_and_update()

    def get_player_count(self) -> int:
        return _BedrockServerStatus("127.0.0.1", self.port_number).status().players.online

    @staticmethod
    def list_online_servers() -> list[str]:
        active_sessions_display = BedrockServer._active_screen_sessions_display()
        return [server for server in SystemUtilities.list_servers() if server in active_sessions_display]

    def check_for_update(self) -> bool:
        return self.last_update_url == self._get_download_url()

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

    def download_and_update(self) -> None:
        download_url = self._get_download_url()
        overwrite_all = False if self.executable_and_properties_exist() else True
        if self.last_update_url == download_url and not overwrite_all:
            return
        try:
            server_zip_response = requests.get(download_url, headers=self._USER_AGENT, timeout=30)
            server_zip_response.raise_for_status()
            server_zip_data = server_zip_response.content
        except requests.Timeout:
            raise TimeoutError("Request for server download timed out.")
        except requests.HTTPError:
            raise ConnectionError("Request for server download unsuccessful.")
        self.last_update_url = download_url
        with ZipFile(BytesIO(server_zip_data)) as server_zip:
            if overwrite_all:
                members = server_zip.namelist()
            else:
                members = [file for file in server_zip.namelist() if file not in self._UPDATER_EXCLUDE_FILES]
                members = [file for file in members for folder in self._UPDATER_EXCLUDE_DIRS if not file.startswith(folder)]
            server_zip.extractall(self.server_subfolder, members=members)
        with open(self.starter_path, "w") as starter_file:
            starter_file.writelines([
                "#!/usr/bin/env bash\n",
                f"cd \"{self.server_subfolder}\"\n",
                "LD_LIBRARY_PATH=. ./bedrock_server"
            ])
        run(["chmod", "+x", self.executable_path], check=True)
        run(["chmod", "+x", self.starter_path], check=True)
