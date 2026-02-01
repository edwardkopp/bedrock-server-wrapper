from bedrock_server import BedrockServer
from sys import argv


def show_help_menu() -> None:
    print("bsw h - Shows this help menu.")
    print("bsw l - Shows a list of servers you have.")
    print("bsw r <server_name> - Starts specified server. If it doesn't exist, it will be created.")
    print("bsw x <server_name> - Stops specified server, but cancels if players are still online.")
    print("bsw k <server_name> - Stops specified server, forcing it to close.")
    print("bsw p <server_name> - Purges specified server, removing all saved data.")
    print("bsw m <server_name> <message> - Messages specified server. Use \"&\" instead of \"§\" for styling, but grammatical use of \"&\" should appear normal.")


def show_server_list() -> None:
    server_list = BedrockServer.list_servers()
    if len(server_list) == 0:
        print("You don't have any servers.")
        return
    print("Here are the servers you have (names case-insensitive):\n")
    for server in BedrockServer.list_servers():
        print(f" * {server}")


def start_server(server_name: str) -> None:
    server = BedrockServer(server_name)
    try:
        server.start()
    except RuntimeError:
        print("Server already running.")
    else:
        print(f"Server started.")
    print(f"If needed, attach to it with \"{server.attach_session_command}\".")


def stop_server(server_name: str, force_stop: bool = False) -> None:
    try:
        BedrockServer(server_name).stop(force_stop)
    except RuntimeError:
        print("Server cannot be stopped as players are still online. Use \"bsw k\" to force stop the server.")
    print("Server stopped." if not force_stop else "Server force stopped.")


def purge_server(server_name: str) -> None:
    try:
        BedrockServer(server_name).purge()
    except RuntimeError:
        print("Server cannot be purged while running. Stop it first with \"bsw x\" or \"bsw k\".")


def send_message_to_server(server_name: str, args: list[str]) -> None:
    try:
        BedrockServer(server_name).message(" ".join(args))
    except RuntimeError:
        print("Server cannot broadcast messages when it is not running. Start it first with \"bsw r\".")


def main() -> None:
    if not BedrockServer.check_screen():
        print("You need screen installed to use this program.")
        return
    try:
        action = argv[1].lower()
    except IndexError:
        show_help_menu()
        return
    arguments = argv[2:]
    if action == "h":
        show_help_menu()
        return
    if action == "l":
        show_server_list()
        return
    if action not in ("r", "x", "k", "p", "m"):
        print("Command not recognized. Use \"bsw h\" for a list of commands.")
    server_name = arguments[0]
    arguments = arguments[1:]
    try:
        valid_server_name = BedrockServer.validate_name(server_name)
    except IndexError:
        print("Target server name must be provided for this command.")
        return
    if not valid_server_name:
        print(f"Server name invalid. Server names must be alphanumeric and {BedrockServer.MIN_NAME_LEN}-{BedrockServer.MAX_NAME_LEN} characters long.")
        return
    match action:
        case "r":
            start_server(server_name)
        case "x":
            stop_server(server_name)
        case "k":
            stop_server(server_name, force_stop=True)
        case "p":
            purge_server(server_name)
        case "m":
            send_message_to_server(server_name, arguments)


if __name__ == "__main__":
    main()
