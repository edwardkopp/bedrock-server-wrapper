from os import listdir
from os.path import join, isfile
from pathlib import Path


class SystemUtilities:

    _DIR = join(Path.home(), ".bedrock_servers")
    _BEDROCK_SERVER_PROGRAM_NAME = "bedrock_server"
    _BEDROCK_SERVER_PROPERTIES_FILE_NAME = "server.properties"

    def __init__(self, server_name: str) -> None:
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

    @property
    def port_number(self) -> int:
        try:
            port = int(self.read_server_properties()["server-port"])
        except TypeError:
            raise TypeError("Server port in server.properties is not an integer.")
        except KeyError:
            raise KeyError("Server port not found in server.properties file.")
        if port < 1024 or port > 65535:
            raise ValueError("Server port value in server.properties is out of range (too high or low).")
        return port

    @staticmethod
    def list_servers() -> list[str]:
        return [server for server in listdir(SystemUtilities._DIR) if SystemUtilities(server).executable_and_properties_exist()]
