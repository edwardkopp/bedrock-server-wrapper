from libtmux import Server as TmuxServer
from ._system import SystemUtilities
from ._update import download_and_place
from subprocess import run
from shutil import rmtree
from time import sleep
from re import sub
from mcstatus import BedrockServer as _BedrockServerStatus


class BedrockServer(SystemUtilities):

    MIN_NAME_LENGTH = 4
    MAX_NAME_LENGTH = 32

    def __init__(self, name: str = "default") -> None:
        name = name.lower()
        if not name.isalnum() and not self.MAX_NAME_LENGTH >= len(name) >= self.MIN_NAME_LENGTH:
            raise ValueError(f"Server name must be alphanumeric and {self.MIN_NAME_LENGTH}-{self.MAX_NAME_LENGTH} characters long.")
        SystemUtilities.__init__(self, name)
        self._tmux = TmuxServer()

    @property
    def _tmux_session_name(self) -> str:
        return f"managed-bedrock-server-{self.name}"

    def start(self) -> None:
        self.download()
        run(["tmux", "new-session", "-d", "-s", self._tmux_session_name])
        sleep(1)
        self.execute(f"./{self.starter_path}")

    def stop(self, force_stop: bool = False) -> None:
        if not self._tmux.has_session(self._tmux_session_name):
            return
        players_online = _BedrockServerStatus("127.0.0.1", self.port_number).status().players.online
        if not force_stop and players_online > 0:
            raise RuntimeError("Cannot stop server while players are online without force stopping.")
        pane = self.execute("stop")
        while pane.display_message("#{pane_dead}", get_text=True) == "0":
            sleep(1)
        self._tmux.kill_session(self._tmux_session_name)

    def allowlist_add(self, name: str) -> None:
        self.execute(f"allowlist add {name}")

    def allowlist_remove(self, name: str) -> None:
        self.execute(f"allowlist remove {name}")

    def allowlist_list(self) -> None:
        self.execute("allowlist list")

    def allowlist_reload(self) -> None:
        self.execute("allowlist reload")

    def permission_list(self) -> None:
        self.execute("permission list")

    def permission_reload(self) -> None:
        self.execute("permission reload")

    def promote(self, name: str) -> None:
        self.execute(f"op {name}")

    def demote(self, name: str) -> None:
        self.execute(f"deop {name}")

    def message(self, message: str) -> None:
        message = sub(r"&(?!\s)", "§", message)
        self.execute(f"say {message}")

    def execute(self, command: str) -> Pane:
        session = self._tmux.find_where({"session_name": self._tmux_session_name})
        if not session:
            raise LookupError("No tmux session found for current server.")
        pane = session.attached_window.attached_pane
        pane.send_keys(f"{command}", suppress_history=True)
        return pane

    def capture(self) -> list[str]:
        session = self._tmux.find_where({"session_name": self._tmux_session_name})
        if not session:
            raise LookupError("No tmux session found for current server.")
        pane = session.attached_window.attached_pane
        return pane.capture_pane()

    def purge(self) -> None:
        if self._tmux.has_session(self._tmux_session_name):
            raise RuntimeError("Cannot purge a running server.")
        rmtree(self.folder, ignore_errors=True)

    def download(self, force_download: bool = False) -> None:
        if self._tmux.has_session(self._tmux_session_name):
            raise RuntimeError("Cannot update a running server.")
        download_and_place(self, force_download)
