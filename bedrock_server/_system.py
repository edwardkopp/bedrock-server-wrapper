from os import listdir
from os.path import join, isfile
from pathlib import Path
from datetime import datetime
from shutil import make_archive
import requests
from zipfile import ZipFile
from io import BytesIO
from subprocess import run
from fake_useragent import UserAgent


class SystemUtilities:

    # File paths and names
    _DIR = join(Path.home(), "BSW")
    _BEDROCK_SERVER_PROGRAM_NAME = "bedrock_server"
    _BEDROCK_SERVER_PROPERTIES_FILE_NAME = "server.properties"

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

    # Empty dictionary to load server.properties into when ready
    _SERVER_PROPERTIES: dict[str, str] = {}

    def __init__(self, server_name: str) -> None:
        Path(self._DIR).mkdir(parents=True, exist_ok=True)
        self.server_name = server_name.lower()

    def _load_server_properties(self) -> None:
        with open(join(self.server_subfolder, self._BEDROCK_SERVER_PROPERTIES_FILE_NAME), "r") as file:
            for line in file:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                key, value = line.split("=", 1)
                self._SERVER_PROPERTIES[key] = value.strip()

    @property
    def folder(self) -> str:
        return join(self._DIR, self.server_name)

    @property
    def server_subfolder(self) -> str:
        return join(self.folder, "server")

    @property
    def backups_subfolder(self) -> str:
        return join(self.folder, "backups")

    @property
    def executable_path(self) -> str:
        return join(self.server_subfolder, self._BEDROCK_SERVER_PROGRAM_NAME)

    def executable_and_properties_exist(self) -> bool:
        starter_exists = isfile(self.starter_path)
        executable_exists = isfile(self.executable_path)
        properties_exists = isfile(join(self.server_subfolder, self._BEDROCK_SERVER_PROPERTIES_FILE_NAME))
        return starter_exists and executable_exists and properties_exists

    @property
    def starter_path(self) -> str:
        return join(self.server_subfolder, "starter.sh")

    @property
    def last_update_url(self) -> str:
        try:
            with open(join(self.folder, "last_update_url.txt"), "r") as file:
                return file.read()
        except FileNotFoundError:
            return ""

    @last_update_url.setter
    def last_update_url(self, url: str) -> None:
        url_path = join(self.folder, "last_update_url.txt")
        Path(url_path).parent.mkdir(parents=True, exist_ok=True)
        with open(url_path, "w") as file:
            file.write(url)

    def get_server_property(self, key: str) -> str | None:
        self._load_server_properties()
        return self._SERVER_PROPERTIES.get(key, None)

    @property
    def lan_visibility(self) -> bool:
        return self.get_server_property("enable-lan-visibility") == "true"

    @property
    def port_number(self) -> int:
        port = self.get_server_property("server-port")
        if port is None:
            raise KeyError("Server port not found in server.properties file.")
        try:
            port = int(port)
        except TypeError:
            raise TypeError("Server port in server.properties is not an integer.")
        if port < 1024 or port > 65535:
            raise ValueError("Server port value in server.properties is out of range (too high or low).")
        return port

    @property
    def port_number_ipv6(self) -> int:
        port = self.get_server_property("server-portv6")
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

    def limit_backups(self, limit: int) -> None:
        backups = self.list_backups()
        if len(backups) <= limit:
            return
        backups.sort(reverse=True)
        for backup in backups[limit:]:
            Path(join(self.backups_subfolder, backup)).unlink()

    def recent_backup_age_minutes(self) -> int | None:
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

    def do_backup(self) -> None:
        backup_name = f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
        backup_path = join(self.backups_subfolder, backup_name)
        Path(self.backups_subfolder).mkdir(parents=True, exist_ok=True)
        make_archive(backup_path, "zip", self.server_subfolder)

    @staticmethod
    def list_servers() -> list[str]:
        return [server for server in listdir(SystemUtilities._DIR) if SystemUtilities(server).executable_and_properties_exist()]

    @staticmethod
    def _get_download_url() -> str:
        try:
            response = requests.get(SystemUtilities._UPDATE_LINKS_URL, headers=SystemUtilities._USER_AGENT, timeout=10)
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

    def check_for_update(self) -> bool:
        return self.last_update_url == self._get_download_url()

    def download_and_place(self, overwrite_all: bool = False) -> None:
        """

            Used to determine where and to download and how to handle updating if server files already exist.
        :param overwrite_all: Boolean indicating if download should overwrite existing files.
        """
        download_url = self._get_download_url()
        if not self.executable_and_properties_exist():
            overwrite_all = True
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
