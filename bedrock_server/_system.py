from os import listdir
from os.path import join, isfile
from pathlib import Path
from platform import system


class SystemUtilities:

    _DIR = join(Path.home(), ".bedrock_servers")
    _BEDROCK_SERVER_PROGRAM_NAME = "bedrock_server"

    def __init__(self, name: str) -> None:
        if not name.isalnum() or len(name) <= 4:
            raise ValueError("Server name must be alphanumeric and more than four characters long.")
        self._name = name.lower()

    @property
    def name(self) -> str:
        return self._name

    @property
    def folder(self) -> str:
        return join(self._DIR, self._name)

    @property
    def server_subfolder(self) -> str:
        return join(self.folder, "server")

    @property
    def backups_subfolder(self) -> str:
        return join(self.folder, "backups")

    @property
    def executable_path(self) -> str:
        return join(self.server_subfolder, self._BEDROCK_SERVER_PROGRAM_NAME)

    def executable_exists(self) -> bool:
        return isfile(self.executable_path) and isfile(self.starter_path)

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

    @staticmethod
    def list_servers() -> list:
        return [server for server in listdir(SystemUtilities._DIR) if SystemUtilities(server).executable_exists()]

    @staticmethod
    def is_windows() -> bool:
        return system().lower() == "windows"
