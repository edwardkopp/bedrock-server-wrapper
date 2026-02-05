from os import listdir
from os.path import join, isfile
from pathlib import Path
from datetime import datetime
from shutil import make_archive


class SystemUtilities:

    _DIR = join(Path.home(), "BSW")
    _BEDROCK_SERVER_PROGRAM_NAME = "bedrock_server"
    _BEDROCK_SERVER_PROPERTIES_FILE_NAME = "server.properties"

    def __init__(self, server_name: str) -> None:
        Path(self._DIR).mkdir(parents=True, exist_ok=True)
        self.server_name = server_name.lower()

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

    def read_server_properties(self) -> dict[str, str]:
        properties = {}
        with open(join(self.server_subfolder, self._BEDROCK_SERVER_PROPERTIES_FILE_NAME), "r") as file:
            for line in file:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                key, value = line.split("=", 1)
                properties[key] = value.strip()
        return dict(properties)

    def get_server_property(self, key: str) -> str | None:
        return self.read_server_properties().get(key, None)

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
