import sys
import argparse
import asyncio
from cl_ai.core import CLAI
from cl_ai.ui import console, configure_interactive, list_conversations, show_conversation
from cl_ai.config import save_config

async def async_main(argv: list = None):
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        description="CL AI - Get bash commands from AI"
    )
    parser.add_argument(
        "query", nargs="*",
        help="Query to send to the AI (omit for interactive mode)"
    )
    parser.add_argument(
        "--config", action="store_true", help="Configure the tool"
    )
    parser.add_argument(
        "-l", "--list", action="store_true", help="List all conversations"
    )
    parser.add_argument(
        "--title", type=str, help="Set a custom title for the conversation"
    )
    parser.add_argument(
        "--continue", dest="continue_conversation", type=str,
        help="Continue a conversation by title or ID"
    )
    parser.add_argument(
        "--continue-last", action="store_true",
        help="Continue the last conversation"
    )
    parser.add_argument(
        "-s", "--show", type=str, help="Show a conversation by title or ID"
    )
    parser.add_argument(
        "--delete", type=str, action="append", help="Delete a conversation by title or ID"
    )

    args = parser.parse_args(argv)
    cl_ai_instance = CLAI()

    if args.config:
        configure_interactive(cl_ai_instance.config, lambda c: save_config(c, console), console)
    elif args.list:
        list_conversations(cl_ai_instance.conversations, console)
    elif args.show:
        show_conversation(cl_ai_instance.conversations, args.show, cl_ai_instance.find_conversation, console)
    elif args.delete:
        for identifier in args.delete:
            cl_ai_instance.delete_conversation(identifier)
    elif args.query:
        conversation_id = None
        if args.continue_last:
            conversation_id = cl_ai_instance.get_latest_conversation_id()
        elif args.continue_conversation:
            conversation_id = cl_ai_instance.find_conversation(args.continue_conversation)

        query_str = " ".join(args.query)
        if not sys.stdin.isatty():
            stdin_content = sys.stdin.read()
            query_str = f"{query_str}\n{stdin_content}"
        await cl_ai_instance.one_shot_mode(query_str, title=args.title, conversation_id=conversation_id)
    else:
        await cl_ai_instance.interactive_mode()


def main():
    """Main entry point for the script."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]An unexpected error occurred: {e}[/red]")
        sys.exit(1)

if __name__ == "__main__":
    main()
