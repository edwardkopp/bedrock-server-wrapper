from ._system import SystemUtilities
from ._update import download_and_place
from subprocess import run
from shutil import rmtree
from re import sub
from mcstatus import BedrockServer as _BedrockServerStatus


class BedrockServer(SystemUtilities):

    MIN_NAME_LEN = 4
    MAX_NAME_LEN = 32

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

    def _check_running(self) -> bool:
        return self._session_name in run(["screen", "-ls"], capture_output=True, text=True).stdout

    @staticmethod
    def validate_name(server_name: str) -> bool:
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
            other_server = SystemUtilities(server_name)
            other_server_ports = (other_server.port_number, other_server.port_number_ipv6)
            if self.port_number in other_server_ports or self.port_number_ipv6 in other_server_ports:
                raise OSError("Server ports conflict with another server.")
        run(["screen", "-dmS", self._session_name, "bash", str(self.starter_path)])

    def stop(self, force_stop: bool = False) -> None:
        if not self._check_running():
            return
        players_online = _BedrockServerStatus("127.0.0.1", self.port_number).status().players.online
        if not force_stop and players_online > 0:
            raise RuntimeError("Cannot stop server while players are online without force stopping.")
        self._execute("stop")

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
        run(["screen", "-S", self._session_name, "-p", 0, "-X", "stuff", f"\"{command.replace("\"", "\\\"")}\n\""])

    def _download(self, force_download: bool = False) -> None:
        if self._check_running():
            raise RuntimeError("Cannot download server while it is running.")
        download_and_place(self, force_download)
