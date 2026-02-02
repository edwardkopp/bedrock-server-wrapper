from bedrock_server import BedrockServer
from typer import Typer, Argument, Option


app = Typer(add_completion=False, rich_markup_mode=None)


@app.command(name="list", help="Shows a list of servers you have.")
def list_servers() -> None:
    server_list = BedrockServer.list_servers()
    if len(server_list) == 0:
        print("You don't have any servers.")
        return
    print("Here are the servers you have (names case-insensitive):")
    for server in BedrockServer.list_servers():
        print(f" -> {server}")


@app.command(help="Creates a new server.")
def new(server_name: str) -> None:
    try:
        BedrockServer(server_name).new()
    except FileExistsError:
        print("Server already exists.")
        return
    print("Server created.")


@app.command(help="Starts the specified server.")
def start(server_name: str) -> None:
    server = BedrockServer(server_name)
    try:
        server.start()
    except RuntimeError:
        print("Server already running.")
    except FileNotFoundError:
        print("Server does not exist.")
        return
    else:
        print(f"Server started.")
    print(f"If needed, attach to it with \"{server.attach_session_command}\".")


@app.command(help="Stops the specified server.")
def stop(server_name: str, force: bool = False) -> None:
    try:
        BedrockServer(server_name).stop(force)
    except RuntimeError:
        print("Server cannot be stopped as players are still online. Use \"bsw k\" to force stop the server.")
        return
    print("Server stopped." if not force else "Server force stopped.")


@app.command(help="Purges the specified server, removing all saved data.")
def purge(server_name: str) -> None:
    try:
        BedrockServer(server_name).purge()
    except RuntimeError:
        print("Server cannot be purged while running.")


@app.command(help="Sends message to chat of the specified server.")
def chat(
        server_name: str,
        message: list[str] = Argument(..., help="Use \"&\" instead of \"§\" for styling, but grammatical use of \"&\" should appear normal.")) -> None:
    try:
        BedrockServer(server_name).message(" ".join(message))
    except RuntimeError:
        print("Server cannot broadcast messages when it is not running.")


@app.command(help="Creates backup of the specified server.")
def backup(
        server_name: str = Argument(help="Name of the server."),
        force: bool = False,
        enforce_cooldown_minutes: int = Option(1, min=1, max=1440, help="Minimum time to enforce between backups."),
        limit: int = Option(100, min=1, max=100, help="Maximum number of backups to keep.")
) -> None:
    BedrockServer(server_name).backup(force_backup=force, enforce_cooldown_minutes=enforce_cooldown_minutes, backup_limit=limit)


if __name__ == "__main__":
    app()
