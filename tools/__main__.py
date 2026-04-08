"""MindGraph CLI — python3 -m tools <subcommand> [args]"""
import sys

COMMANDS = {
    "init": "tools.init_kb",
    "fingerprint": "tools.fingerprint",
    "search": "tools.search",
    "ingest": "tools.ingest",
    "lint": "tools.lint",
    "watch": "tools.watch",
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: python3 -m tools <subcommand> [args]")
        print(f"\nSubcommands: {', '.join(COMMANDS)}")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd not in COMMANDS:
        print(f"Unknown command: {cmd}")
        print(f"Available: {', '.join(COMMANDS)}")
        sys.exit(1)

    sys.argv = sys.argv[1:]
    module = __import__(COMMANDS[cmd], fromlist=["main"])
    module.main()


if __name__ == "__main__":
    main()
