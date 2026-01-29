from libtmux import Server as TmuxServer, Pane
from libtmux.exc import TmuxCommandNotFound
from ._system import SystemUtilities
from ._update import download_and_place
from subprocess import run
from shutil import rmtree
from time import sleep
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
        if not server_name.isalnum() and not self.MAX_NAME_LEN >= len(server_name) >= self.MIN_NAME_LEN:
            raise ValueError(f"Server name must be alphanumeric and {self.MIN_NAME_LEN}-{self.MAX_NAME_LEN} characters long.")
        SystemUtilities.__init__(self, server_name)
        self._tmux = TmuxServer()

    @staticmethod
    def validate_name(server_name: str) -> bool:
        return server_name.isalnum() and BedrockServer.MIN_NAME_LEN <= len(server_name) <= BedrockServer.MAX_NAME_LEN

    @staticmethod
    def check_tmux() -> bool:
        """
        Method to check if tmux is installed on the system.

        :return: Boolean indicating True if tmux is installed, or False if it is not installed.
        """
        server = TmuxServer()
        try:
            _ = server.sessions
        except TmuxCommandNotFound:
            return False
        return True

    @property
    def _tmux_session_name(self) -> str:
        return f"bsw-{self.server_name}"

    @property
    def tmux_attach_session_command(self) -> str:
        if not self._tmux.has_session(self._tmux_session_name):
            raise RuntimeError("Cannot attach when the server is not running.")
        return f"tmux a -t {self._tmux_session_name}"

    def start(self) -> None:
        self._download()
        run(["tmux", "new-session", "-d", "-s", self._tmux_session_name])
        sleep(1)
        self._execute(f"./{self.starter_path}")

    def stop(self, force_stop: bool = False) -> None:
        if not self._tmux.has_session(self._tmux_session_name):
            return
        players_online = _BedrockServerStatus("127.0.0.1", self.port_number).status().players.online
        if not force_stop and players_online > 0:
            raise RuntimeError("Cannot stop server while players are online without force stopping.")
        pane = self._execute("stop")
        while pane.display_message("#{pane_dead}", get_text=True) == "0":
            sleep(1)
        self._tmux.kill_session(self._tmux_session_name)

    def message(self, message: str) -> None:
        message = sub(r"&(?!\s)", "§", message)
        try:
            self._execute(f"say {message}")
        except LookupError:
            raise RuntimeError("Cannot send message when the server is not running.")

    def purge(self) -> None:
        if self._tmux.has_session(self._tmux_session_name):
            raise RuntimeError("Cannot purge a running server.")
        rmtree(self.folder, ignore_errors=True)

    def _execute(self, command: str) -> Pane:
        session = self._tmux.sessions.get(session_name=self._tmux_session_name)
        if not session:
            raise LookupError("No tmux session found for current server.")
        pane = session.attached_window.attached_pane
        pane.send_keys(f"{command}", suppress_history=True)
        return pane

    def _download(self, force_download: bool = False) -> None:
        if self._tmux.has_session(self._tmux_session_name):
            raise RuntimeError("Cannot update a running server.")
        download_and_place(self, force_download)
