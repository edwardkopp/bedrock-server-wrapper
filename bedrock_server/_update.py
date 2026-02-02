import requests
from zipfile import ZipFile
from io import BytesIO
from subprocess import run
from ._system import SystemUtilities
from fake_useragent import UserAgent


_LINKS_URL = "https://net-secondary.web.minecraft-services.net/api/v1.0/download/links"
_HEADERS = {
    "User-Agent": UserAgent(platforms=["desktop"]).random
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


def download_and_place(server_utilities_object: SystemUtilities, overwrite_all: bool = False) -> None:
    """

    :param server_utilities_object: SystemUtilities object.
        Used to determine where and to download and how to handle updating if server files already exist.
    :param overwrite_all: Boolean indicating if download should overwrite existing files.
    :raises TimeoutError: If requests to download servers timeout.
    :raises ConnectionError: If requests to download servers fail.
    """
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
        if url_data["downloadType"] == "serverBedrockLinux":
            server_download_url = url_data["downloadUrl"]
    if server_download_url is None:
        raise KeyError("No download URL for Linux server found.")
    if not server_utilities_object.executable_and_properties_exist():
        overwrite_all = True
    if server_utilities_object.last_update_url == server_download_url and not overwrite_all:
        return
    try:
        server_zip_response = requests.get(server_download_url, headers=_HEADERS, timeout=30)
        server_zip_response.raise_for_status()
        server_zip_data = server_zip_response.content
    except requests.Timeout:
        raise TimeoutError("Request for server download timed out.")
    except requests.HTTPError:
        raise ConnectionError("Request for server download unsuccessful.")
    server_utilities_object.last_update_url = server_download_url
    with ZipFile(BytesIO(server_zip_data)) as server_zip:
        if overwrite_all:
            members = server_zip.namelist()
        else:
            members = [file for file in server_zip.namelist() if file not in _EXCLUDE_FILES]
            members = [file for file in members for folder in _EXCLUDE_DIRS if not file.startswith(folder)]
        server_zip.extractall(server_utilities_object.server_subfolder, members=members)
    with open(server_utilities_object.starter_path, "w") as starter_file:
        starter_file.writelines([
            "#!/usr/bin/env bash\n",
            f"cd \"{server_utilities_object.server_subfolder}\"\n",
            "LD_LIBRARY_PATH=. ./bedrock_server"
        ])
    run(["chmod", "+x", server_utilities_object.executable_path], check=True)
    run(["chmod", "+x", server_utilities_object.starter_path], check=True)
