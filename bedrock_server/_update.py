import requests
from zipfile import ZipFile
from io import BytesIO
from subprocess import run
from ._system import SystemUtilities


_LINKS_URL = "https://net-secondary.web.minecraft-services.net/api/v1.0/download/links"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
}
_EXCLUDE_FILES = [
    "allowlist.json",
    "packetlimitconfig.json",
    "permissions.json",
    "profanity_filter.wlist",
    "server.properties"
]
_EXCLUDE_DIRS = [
    "config"
]


def download_and_place(server_path: SystemUtilities, force_download: bool = False) -> None:
    try:
        response = requests.get(_LINKS_URL, headers=_HEADERS, timeout=10)
        response.raise_for_status()
        urls_data: dict = response.json()
    except requests.Timeout:
        raise TimeoutError("Request for download links timed out.")
    except requests.HTTPError:
        raise ConnectionError("Request for download links unsuccessful.")
    urls_data: list[dict] = urls_data["result"]["links"]
    server_download_url: str | None = None
    for url_data in urls_data:
        if url_data["downloadType"] == "serverBedrockLinux":  # Use serverBedrockWindows if wanting Windows, but I'd rather use Linux
            server_download_url = url_data["downloadUrl"]
    if server_download_url is None:
        raise KeyError("No download URL for Linux server found.")
    if server_path.last_update_url == server_download_url and not force_download:
        return
    try:
        server_zip_response = requests.get(server_download_url, headers=_HEADERS, timeout=30)
        server_zip_response.raise_for_status()
        server_zip_data = server_zip_response.content
    except requests.Timeout:
        raise TimeoutError("Request for server download timed out.")
    except requests.HTTPError:
        raise ConnectionError("Request for server download unsuccessful.")
    server_path.last_update_url = server_download_url
    with ZipFile(BytesIO(server_zip_data)) as server_zip:
        members = [file for file in server_zip.namelist() if file not in _EXCLUDE_FILES]
        members = [file for file in members for folder in _EXCLUDE_DIRS if not file.startswith(folder)]
        server_zip.extractall(server_path.server_subfolder, members=members)
    with open(server_path.starter_path, "w") as starter_file:
        starter_file.writelines([
            "#!/usr/bin/env bash\n",
            f"cd \"{server_path.server_subfolder}\"\n",
            "LD_LIBRARY_PATH=. ./bedrock_server"
        ])
    if not server_path.is_windows():
        run(["chmod", "+x", server_path.executable_path], check=True)
        run(["chmod", "+x", server_path.starter_path], check=True)
