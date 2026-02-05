from bedrock_server import BedrockServer
import typer as ty


app = ty.Typer(add_completion=False)


@app.command(name="list", help="Shows a list of servers you have.")
def list_servers() -> None:
    server_list = BedrockServer.list_servers()
    online_server_list = BedrockServer.list_online_servers()
    if len(server_list) == 0:
        print("You don't have any servers.")
        return
    print("Here are the servers you have (names case-insensitive):\n")
    for server in server_list:
        server_object = BedrockServer(server)
        print(f" -> Name: {server}")
        print(f"    Ports: {server_object.port_number} (IPv4), {server_object.port_number_ipv6} (IPv6)")
        if server in online_server_list:
            print(f"    RUNNING: {server_object.get_player_count()} online. Use \"{server_object.attach_session_command}\" to attach.")
        else:
            print("    OFFLINE")
    if len(online_server_list):
        print("\nTo detach from a server's screen session, the default keybind is Ctrl+A then D.")


@app.command(help="Creates a new server.")
def new(server_name: str) -> None:
    try:
        server_name = server_name.lower()
        BedrockServer(server_name).new()
    except FileExistsError:
        print("Server already exists.")
        return
    except ValueError:
        print("Server name is invalid.")
        return
    print(f"Server created.")
    print(f"Configuration files can be found at: {BedrockServer(server_name).server_subfolder}")


@app.command(help="Shows the directory of where the server is stored, or where backups are stored.")
def where(server_name: str, backups: bool = False) -> None:
    try:
        server = BedrockServer(server_name)
    except FileNotFoundError:
        print("Server does not exist.")
        return
    except ValueError:
        print("Server name is invalid.")
        return
    if backups:
        print(server.backups_subfolder)
        return
    print(server.server_subfolder)


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
    except ValueError:
        print("Server name is invalid.")
        return
    except OSError:
        print("Potential ports conflict. Please check the following in server.properties:")
        print(" -> Ensure that no other server is using the same ports.")
        print(" -> Ensure enable-lan-visibility is set to false.")
        return
    else:
        print(f"Server started.")
    print(f"If needed, attach to it with \"{server.attach_session_command}\".")
    print("To detach from a server's screen session, the default is Ctrl+A then D.")


@app.command(help="Stops the specified server.")
def stop(server_name: str, force: bool = False) -> None:
    try:
        BedrockServer(server_name).stop(force)
    except ValueError:
        print("Server name is invalid.")
        return
    except RuntimeError:
        print("Server cannot be stopped as players are still online. Use the force option to do it anyway.")
        return
    print("Server stopped." if not force else "Server force stopped.")


@app.command(help="Purges the specified server, removing all saved data.")
def purge(server_name: str) -> None:
    if server_name not in BedrockServer.list_servers():
        print("Server does not exist.")
        return
    if server_name in BedrockServer.list_online_servers():
        print("Server cannot be purged while running.")
        return
    if not ty.confirm("Are you sure you want to purge the server? This cannot be undone."):
        print("Operation canceled.")
        return
    try:
        BedrockServer(server_name).purge()
    except RuntimeError:
        print("Server cannot be purged while running.")
        return
    print("Server purged.")


@app.command(help="Sends message to chat of the specified server.")
def chat(
        server_name: str,
        message: str = ty.Argument(help="Use \"&\" instead of \"§\" for styling, but grammatical use of \"&\" should appear normal.")) -> None:
    if server_name not in BedrockServer.list_servers():
        print("Server does not exist.")
        return
    elif server_name not in BedrockServer.list_online_servers():
        print("Server is not running.")
        return
    try:
        BedrockServer(server_name).message(message)
    except RuntimeError:
        print("Server cannot broadcast messages when it is not running.")
    else:
        print("Message sent.")


@app.command(help="Creates backup of the specified server.")
def backup(
        server_name: str = ty.Argument(help="Name of the server."),
        force: bool = False,
        cooldown: int = ty.Option(60, min=0, max=720, help="If the previous backup was less than this many minutes ago, the backup will be skipped."),
        limit: int = ty.Option(30, min=1, max=100, help="Maximum number of backups to keep.")
) -> None:
    if server_name not in BedrockServer.list_servers():
        print("Server does not exist.")
        return
    try:
        BedrockServer(server_name).backup(enforce_cooldown_minutes=cooldown, backup_limit=limit, force_backup=force)
    except FileExistsError:
        print("Previous backup is too recent. No backup created.")
    except RuntimeError:
        print("Server cannot be backed up as players are still online. Use the force option to do it anyway.")
    else:
        print("Backup created.")


def main() -> None:
    if not BedrockServer.check_screen():
        print("screen is not installed. Please install it before using this program.")
        return
    app()


if __name__ == "__main__":
    main()
