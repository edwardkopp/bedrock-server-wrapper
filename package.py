from PyInstaller.__main__ import run
from sys import platform

from setuptools.errors import PlatformError

APP_NAME = "bsw"
MAIN_PY = "main.py"


def package() -> None:
    if platform != "linux":
        raise PlatformError("This program is Linux only.")
    run([
        "--clean", "-y",
        "-n", APP_NAME,
        "-w", MAIN_PY
    ])


if __name__ == "__main__":
    package()
