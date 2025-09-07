from bedrock_server import BedrockServer
from sys import argv


def main() -> None:
    arguments = argv[1:]
    if arguments[0].lower() in ("help", "h"):
        return
    if len(arguments) < 2:
        print("Not enough arguments.")
    BedrockServer("default").download()


if __name__ == "__main__":
    main()
