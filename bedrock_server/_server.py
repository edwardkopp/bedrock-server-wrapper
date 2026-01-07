from libtmux import Server as TmuxServer
from ._system import SystemUtilities
from ._update import download_and_place
from subprocess import run
from shutil import rmtree
from time import sleep
from re import sub
from mcstatus import BedrockServer as _BedrockServerStatus


class BedrockServer(SystemUtilities):

    def __init__(self, name: str = "default") -> None:
        name = name.lower()
        if name.isalpha() and len(name) <= 4:
            raise ValueError("Server name must be letters only and more than four characters long.")
        SystemUtilities.__init__(self, name)
        self._tmux = TmuxServer()

    def start(self) -> None:
        self.download()
        run(["tmux", "new-session", "-d", "-s", self.name])
        sleep(1)
        self.execute(f"./{self.starter_path}")

    def stop(self, force_stop: bool = False) -> None:
        players_online = _BedrockServerStatus("127.0.0.1", self.port_number).status().players.online
        if not force_stop and players_online > 0:
            raise RuntimeError("Cannot stop server while players are online without force stopping.")
        self.execute("stop")

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

    def execute(self, command: str) -> None:
        session = self._tmux.find_where({"session_name": self.name})
        if session:
            pane = session.attached_window.attached_pane
            pane.send_keys(f"{command}\n", suppress_history=True)
        else:
            raise RuntimeError("No tmux session found for current server.")

    def capture(self) -> list[str]:
        session = self._tmux.find_where({"session_name": self.name})
        if session:
            pane = session.attached_window.attached_pane
            return pane.capture_pane()
        else:
            raise RuntimeError("No tmux session found for current server.")

    @staticmethod
    def purge(name: str) -> None:
        rmtree(SystemUtilities(name).folder, ignore_errors=True)

    def download(self, force_download: bool = False) -> None:
        download_and_place(self, force_download)
