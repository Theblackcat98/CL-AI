#!/usr/bin/env python3

import json
import os
import sys
import asyncio
import subprocess  # Added for subprocess.run
import aiohttp
from typing import Dict, List, Any
import argparse
import readline  # For command history
import re  # For extract_command
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table


# Simple config
DEFAULT_CONFIG = {
    "model": "phi4:latest",  # Or your preferred default model
    "url": "http://localhost:11434/api",  # Adjust if Ollama runs elsewhere
    "type": "ollama",
    "prompt_prefix": (
        "You are a helpful assistant that provides accurate bash commands for "
        "Linux. ONLY output the command. The command MUST be enclosed in a "
        "bash markdown code block (e.g., ```bash\\ncommand --option\\n```). "
        "Do NOT provide any explanation or any other text outside the code "
        "block unless explicitly asked. If you cannot provide a command, "
        "explain why in plain text without any code blocks."
    ),
    "auto_run_prompt": True
}

CONFIG_FILE = os.path.expanduser("~/.cl_ai_config.json")  # Renamed
CONVERSATIONS_FILE = os.path.expanduser("~/.cl_ai_conversations.json")

console = Console()


class CLAI:  # Renamed class
    def __init__(self):
        self.config = self.load_config()
        self.conversations = self.load_conversations()

    def load_config(self) -> Dict[str, Any]:
        """Load config from file or use defaults."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config_data = json.load(f)
                    # Basic validation: check if it's a dictionary
                    if not isinstance(config_data, dict):
                        console.print(
                            f"[red]Error: Config file ({CONFIG_FILE}) "
                            f"does not contain a valid JSON object. Using "
                            f"default configuration.[/red]"
                        )
                        return DEFAULT_CONFIG
                    # You could add more specific key checks here if needed
                    return config_data
            except json.JSONDecodeError as e:
                console.print(
                    f"[red]Error decoding config file ({CONFIG_FILE}): {e}. "
                    f"Using default configuration.[/red]"
                )
                return DEFAULT_CONFIG
            except PermissionError as e:
                console.print(
                    f"[red]Permission error reading config file "
                    f"({CONFIG_FILE}): {e}. Using default "
                    f"configuration.[/red]"
                )
                return DEFAULT_CONFIG
            except Exception as e:  # Catch any other unexpected errors
                console.print(
                    f"[red]Unexpected error loading config file "
                    f"({CONFIG_FILE}): {e}. Using default "
                    f"configuration.[/red]"
                )
                return DEFAULT_CONFIG

        # Config file does not exist, create it with default settings
        console.print(
            f"[yellow]Config file not found at {CONFIG_FILE}. "
            f"Creating with default settings.[/yellow]"
        )
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(DEFAULT_CONFIG, f, indent=2)
            return DEFAULT_CONFIG
        except PermissionError as e:
            console.print(
                f"[red]Permission error writing default config file "
                f"({CONFIG_FILE}): {e}. Using in-memory default "
                f"configuration for this session.[/red]"
            )
            return DEFAULT_CONFIG  # Return default config in memory
        except Exception as e:
            console.print(
                f"[red]Unexpected error saving default config file "
                f"({CONFIG_FILE}): {e}. Using in-memory default "
                f"configuration for this session.[/red]"
            )
            return DEFAULT_CONFIG

    def load_conversations(self) -> Dict[str, Any]:
        """Load conversations from file."""
        if os.path.exists(CONVERSATIONS_FILE):
            try:
                with open(CONVERSATIONS_FILE, "r") as f:
                    conversations_data = json.load(f)
                    if not isinstance(conversations_data, dict):
                        console.print(
                            f"[yellow]Warning: Conversations file ({CONVERSATIONS_FILE}) "
                            f"does not contain a valid JSON object. Starting "
                            f"with empty conversations.[/yellow]"
                        )
                        return {}
                    return conversations_data
            except json.JSONDecodeError as e:
                console.print(
                    f"[yellow]Warning: Error decoding conversations file "
                    f"({CONVERSATIONS_FILE}): {e}. Starting with empty "
                    f"conversations.[/yellow]"
                )
                return {}
            except PermissionError as e:
                console.print(
                    f"[yellow]Warning: Permission error reading conversations file "
                    f"({CONVERSATIONS_FILE}): {e}. Starting with empty "
                    f"conversations.[/yellow]"
                )
                return {}
            except Exception as e:
                console.print(
                    f"[yellow]Warning: Unexpected error loading conversations file "
                    f"({CONVERSATIONS_FILE}): {e}. Starting with empty "
                    f"conversations.[/yellow]"
                )
                return {}
        return {}

    def save_conversations(self):
        """Save conversations to file."""
        try:
            with open(CONVERSATIONS_FILE, "w") as f:
                json.dump(self.conversations, f, indent=2)
        except PermissionError as e:
            console.print(
                f"[red]Error saving conversations to {CONVERSATIONS_FILE}: {e}[/red]"
            )
        except Exception as e:
            console.print(
                f"[red]Unexpected error saving conversations: {e}[/red]"
            )

    async def query_llm(self, prompt: str, conversation_id: str = None) -> str:
        """Query the LLM for a response."""
        messages = []

        # Add system message with prefix
        messages.append({
            "role": "system",
            "content": self.config["prompt_prefix"]
        })

        if conversation_id and conversation_id in self.conversations:
            for message in self.conversations[conversation_id]["messages"]:
                messages.append(message)

        # Add current prompt
        messages.append({
            "role": "user",
            "content": prompt
        })

        # Set up the API request
        if self.config["type"] == "ollama":
            payload = {
                "model": self.config["model"],
                "messages": messages,
                "stream": False
            }

            progress_description = "[progress.description]{task.description}"
            progress_console = Console(stderr=True) if not sys.stdout.isatty() else console
            with Progress(
                SpinnerColumn(),
                TextColumn(progress_description),
                transient=True,
                console=progress_console,
            ) as progress:
                progress.add_task(description="Thinking...", total=None)
                try:
                    async with aiohttp.ClientSession() as session:
                        api_url = f"{self.config['url']}/chat"
                        async with session.post(api_url, json=payload) as resp:
                            if resp.status != 200:
                                error_text = await resp.text()
                                err_msg = (f"Error: HTTP {resp.status} - "
                                           f"{error_text}")
                                return err_msg

                            result = await resp.json()
                            content = result.get("message", {}).get("content")
                            return content if content else "No response"

                except aiohttp.ClientError as e:
                    return f"Connection error: {str(e)}"
                except Exception as e:  # Catch generic exceptions
                    return f"Error: {str(e)}"
        else:
            return "Only Ollama is supported currently."

    def configure(self):
        """Configure the tool interactively."""
        run_prompt_status = self.config.get('auto_run_prompt', True)
        run_prompt_text = 'Enabled' if run_prompt_status else 'Disabled'
        prompt_display_limit = 50
        prompt_preview = self.config['prompt_prefix'][:prompt_display_limit]
        if len(self.config['prompt_prefix']) > prompt_display_limit:
            prompt_preview += "..."

        panel_content = (
            f"Current model: [bold]{self.config['model']}[/bold]\n"
            f"Current API URL: [bold]{self.config['url']}[/bold]\n"
            f"Run command prompt: [bold]{run_prompt_text}[/bold]\n"
            f"Current prompt: [bold]{prompt_preview}[/bold]"
        )
        console.print(Panel(
            Text.from_markup(panel_content),
            title="[cyan]CL AI Configuration[/cyan]",  # Renamed
            expand=False
        ))

        menu_text = (
            "What would you like to change?\n"
            "  1. Model name\n"
            "  2. API URL\n"
            "  3. Prompt prefix\n"
            "  4. Toggle run command prompt\n"
            "  5. Save and exit"
        )
        console.print(Text.from_markup(menu_text))
        choice = Prompt.ask(
            "\nEnter your choice (1-5)", default="5", show_default=False
        )

        made_change = False
        if choice == "1":
            new_model = Prompt.ask(
                "Enter new model name", default=self.config["model"]
            )
            if new_model != self.config["model"]:
                self.config["model"] = new_model
                made_change = True
        elif choice == "2":
            new_url = Prompt.ask(
                "Enter new API URL", default=self.config["url"]
            )
            if new_url != self.config["url"]:
                self.config["url"] = new_url
                made_change = True
        elif choice == "3":
            console.print(Text.from_markup(
                f"\nCurrent prompt prefix:\n"
                f"[italic]{self.config['prompt_prefix']}[/italic]"
            ))
            new_prefix = Prompt.ask(
                "Enter new prompt prefix",
                default=self.config["prompt_prefix"]
            )
            if new_prefix != self.config["prompt_prefix"]:
                self.config["prompt_prefix"] = new_prefix
                made_change = True
        elif choice == "4":
            current_auto_run = self.config.get("auto_run_prompt", True)
            self.config["auto_run_prompt"] = not current_auto_run
            status_msg = ('disabled' if current_auto_run else 'enabled')
            console.print(
                f"[green]Run command prompt {status_msg}.[/green]"
            )
            made_change = True  # Toggling is always a change
        elif choice == "5":
            # Save and exit, user might want to ensure current state is
            # written.
            pass
        else:
            console.print(
                "[red]Invalid choice. Configuration not saved.[/red]"
            )
            return  # Exit without saving for invalid choice

        if made_change or choice == "5":
            try:
                with open(CONFIG_FILE, "w") as f:
                    json.dump(self.config, f, indent=2)
                console.print("[green]Configuration saved.[/green]")
            except PermissionError as e:
                err_msg = (f"[red]Error saving configuration to "
                           f"{CONFIG_FILE}: {e}[/red]")
                console.print(err_msg)
            except Exception as e:
                console.print(
                    f"[red]Unexpected error saving configuration: {e}[/red]"
                )
        elif not made_change:
            console.print("[yellow]No changes made to configuration.[/yellow]")

    def show_help(self):
        """Show help information."""
        help_items = [
            "This tool helps you find the right bash commands by asking an "
            "AI.\n",
            "[bold]Available commands:[/bold]",
            "  [boldmagenta]!config[/boldmagenta]  - Configure CL AI",
            "  [boldmagenta]!help[/boldmagenta]   - Show this help",
            "  [boldmagenta]!history[/boldmagenta] - Show command history",
            "  [boldmagenta]!clear[/boldmagenta]  - Clear command history",
            "  [boldmagenta]!quit[/boldmagenta]   - Exit CL AI\n",  # Renamed
            "Or just type your question about a bash command and press "
            "Enter.\n"
        ]
        help_text_content = "\n".join(help_items)
        help_text = Text.from_markup(help_text_content)

        auto_run = self.config.get("auto_run_prompt", True)
        status_color = "green" if auto_run else "red"
        enabled_str = "" if auto_run else "not "
        status_text_str = (
            f"\nCommand execution prompt is currently [{status_color}]"
            f"{enabled_str}enabled[/{status_color}]."
        )
        help_text.append(Text.from_markup(status_text_str))

        help_text.append(Text.from_markup(
            "\nWhen enabled, you'll be asked whether to run each command "
            "after receiving it."
        ))
        help_text.append(Text.from_markup(
            "You can toggle this feature in the configuration menu (!config)."
        ))

        example_items = [
            "\n\n[bold]Examples:[/bold]",
            "  How do I find files modified in the last 24 hours?",
            "  What's the command to check disk space usage?",
            "  How can I extract a tar.gz file?"
        ]
        help_text.append(Text.from_markup("\n".join(example_items)))

        console.print(
            Panel(
                help_text, title="[cyan]CL AI Help[/cyan]",  # Renamed
                expand=False
            )
        )

    def list_conversations(self):
        """List all conversations."""
        if not self.conversations:
            console.print("[yellow]No conversations found.[/yellow]")
            return

        table = Table(title="[cyan]Conversations[/cyan]")
        table.add_column("ID", style="dim", width=10)
        table.add_column("Title", style="green")

        for conv_id, conv_data in self.conversations.items():
            table.add_row(conv_id, conv_data["title"])

        console.print(table)

    def show_conversation(self, identifier: str):
        """Show a conversation by title or ID."""
        conv_id = self.find_conversation(identifier)
        if not conv_id:
            console.print(f"[red]Conversation '{identifier}' not found.[/red]")
            return

        conv_data = self.conversations[conv_id]
        table = Table(title=f"Conversation: {conv_data['title']} ({conv_id})")
        table.add_column("Role", style="dim", width=10)
        table.add_column("Message", style="green")

        for message in conv_data["messages"]:
            table.add_row(message["role"], message["content"])

        console.print(table)

    def delete_conversation(self, identifier: str):
        """Delete a conversation by title or ID."""
        conv_id = self.find_conversation(identifier)
        if not conv_id:
            console.print(f"[red]Conversation '{identifier}' not found.[/red]")
            return

        del self.conversations[conv_id]
        self.save_conversations()
        console.print(f"[green]Conversation '{identifier}' deleted.[/green]")

    def find_conversation(self, identifier: str) -> str:
        """Find a conversation by title or partial ID."""
        if identifier in self.conversations:
            return identifier

        for conv_id, conv_data in self.conversations.items():
            if conv_data["title"] == identifier:
                return conv_id

        # Match partial ID
        matches = [conv_id for conv_id in self.conversations if conv_id.startswith(identifier)]
        if len(matches) == 1:
            return matches[0]

        return None

    def get_latest_conversation_id(self) -> str:
        """Get the ID of the most recent conversation."""
        if not self.conversations:
            return None
        return list(self.conversations.keys())[-1]

    def extract_command(self, response: str) -> str:
        """
        Extract the command from the LLM response text.

        Prioritizes bash code blocks, then generic code blocks.
        As a fallback, returns the first non-empty line if no code block
        is found, or the entire stripped response if it's a single line.
        """
        # Attempt to find a bash code block
        bash_pattern = r'```bash\s*(.*?)\s*```'
        bash_match = re.search(bash_pattern, response,
                               re.DOTALL | re.IGNORECASE)
        if bash_match:
            extracted_text = bash_match.group(1).strip()
            if extracted_text.startswith("$"):
                return extracted_text[1:].lstrip()
            return extracted_text

        # If no bash block, attempt to find a generic code block
        generic_pattern = r'```\s*(.*?)\s*```'
        generic_match = re.search(generic_pattern, response, re.DOTALL)
        if generic_match:
            extracted_text = generic_match.group(1).strip()
            if extracted_text.startswith("$"):
                return extracted_text[1:].lstrip()
            return extracted_text

        # Fallback strategy
        lines = [line for line in response.split('\n') if line.strip()]
        extracted_text = ""

        if len(lines) == 1:  # Single line of text
            extracted_text = lines[0].strip()
        elif lines:  # Multiple lines, no code block
            # Current prompt aims to prevent this.
            # Extracting the first non-empty line as a heuristic.
            console.print(
                "[yellow]Warning: LLM response had multiple lines without a "
                "code block. Extracting the first non-empty line.[/yellow]"
            )
            extracted_text = lines[0].strip()
        else:  # Handles empty or whitespace-only original response
            extracted_text = response.strip()

        # Final '$' stripping, handles "$ cmd" and "$cmd"
        if extracted_text.startswith("$"):
            # Remove '$' and then any leading spaces from the command
            return extracted_text[1:].lstrip()
        return extracted_text

    def run_command(self, command: str) -> None:
        """Run a command in the shell."""
        try:
            console.print(
                f"[yellow]Executing: [bold]{command}[/bold][/yellow]"
            )
            # Using subprocess.run for better security and control
            result = subprocess.run(
                command, shell=True, check=False, text=True,
                capture_output=True
            )
            if result.stdout:
                console.print(Text(result.stdout.strip()))
            if result.stderr:
                error_output = Text(f"[red]Error output:[/red]\n"
                                    f"{result.stderr.strip()}")
                console.print(error_output)
            if result.returncode != 0:
                console.print(
                    f"[red]Command failed with exit code "
                    f"{result.returncode}[/red]"
                )
        except Exception as e:
            console.print(f"[red]Error executing command: {e}[/red]")

    async def process_command(self, command_str: str, conversation_id: str = None):
        """Process a user command."""
        command_str = command_str.strip()

        if not command_str:
            return True, conversation_id

        if command_str == "!help":
            self.show_help()
        elif command_str == "!config":
            self.configure()
        elif command_str == "!quit":
            console.print("[green]Goodbye![/green]")
            return False, conversation_id
        else:
            response = await self.query_llm(command_str, conversation_id)
            console.print(f"\n[blue]{response}[/blue]\n")

            if not conversation_id:
                conversation_id = os.urandom(4).hex()
                self.conversations[conversation_id] = {
                    "title": command_str.split('\n')[0],
                    "messages": [],
                }

            self.conversations[conversation_id]["messages"].append(
                {"role": "user", "content": command_str}
            )
            self.conversations[conversation_id]["messages"].append(
                {"role": "assistant", "content": response}
            )
            self.save_conversations()

            if self.config.get("auto_run_prompt", True):
                extracted_cmd = self.extract_command(response)
                separator = Text.from_markup(
                    "[yellow]───────────────────────────────────[/yellow]"
                )
                console.print(separator)
                console.print(Text.from_markup(
                    f"[yellow]Extracted command:[/] "
                    f"[bold]{extracted_cmd}[/bold]"
                ))
                run_prompt = Prompt.ask(
                    Text.from_markup(
                        "[yellow]Execute? [/][green]y[/green]/[red]n[/red]"
                    ),
                    choices=["y", "n"], default="n"
                )
                if run_prompt.lower() == 'y':
                    console.print(separator)
                    self.run_command(extracted_cmd)
                else:
                    console.print("[yellow]Command not executed.[/yellow]")
        return True, conversation_id

    async def interactive_mode(self):
        """Run in interactive mode."""
        # Set up readline history
        readline_history_path = os.path.expanduser(
            "~/.cl_ai_readline_history"  # Renamed
        )
        if os.path.exists(readline_history_path):
            try:
                readline.read_history_file(readline_history_path)
            except Exception as e:  # Catch potential errors reading history
                console.print(
                    f"[yellow]Could not load readline history: {e}[/yellow]"
                )

        welcome_message_text = (
            f"CL AI - Ask for bash commands (type !help for help)\n"  # Renamed
            f"Using model: [bold]{self.config['model']}[/bold]"
        )
        console.print(
            Panel(
                Text.from_markup(welcome_message_text),
                title="[cyan]Welcome to CL AI[/cyan]",  # Renamed
                expand=False
            )
        )

        running = True
        conversation_id = None
        while running:
            try:
                prompt_text = Text.from_markup(
                    "[green]cl-ai>[/green]"  # Renamed
                )
                command_input = Prompt.ask(prompt_text)
                running, conversation_id = await self.process_command(command_input, conversation_id)
            except KeyboardInterrupt:
                console.print("\nExiting...")
                break
            except EOFError:  # Handle Ctrl+D
                console.print("\nExiting...")
                break
            except Exception as e:  # Catch other potential errors
                console.print(f"[red]An error occurred: {e}[/red]")
                # Decide if you want to break or continue
                # For now, let's continue
                pass

        # Save readline history
        try:
            readline.write_history_file(readline_history_path)
        except Exception as e:  # Catch potential errors writing history
            console.print(
                f"[yellow]Could not save readline history: {e}[/yellow]"
            )

    async def one_shot_mode(self, query: str, title: str = None, conversation_id: str = None):
        """Run in one-shot mode for a single query."""
        original_messages = []
        if conversation_id and conversation_id in self.conversations:
            original_messages = self.conversations[conversation_id]["messages"]

        response = await self.query_llm(query, conversation_id)
        console.print(f"\n[blue]{response}[/blue]\n")

        if title and conversation_id:
            # Branching: create a new conversation with a new title
            new_conv_id = os.urandom(4).hex()
            self.conversations[new_conv_id] = {
                "title": title,
                "messages": original_messages + [
                    {"role": "user", "content": query},
                    {"role": "assistant", "content": response},
                ],
            }
        elif conversation_id:
            # Continuing an existing conversation
            self.conversations[conversation_id]["messages"].append({"role": "user", "content": query})
            self.conversations[conversation_id]["messages"].append({"role": "assistant", "content": response})
        else:
            # Starting a new conversation
            new_conv_id = os.urandom(4).hex()
            self.conversations[new_conv_id] = {
                "title": title if title else query.split('\n')[0],
                "messages": [
                    {"role": "user", "content": query},
                    {"role": "assistant", "content": response},
                ],
            }
        self.save_conversations()

        if self.config.get("auto_run_prompt", True):
            extracted_cmd = self.extract_command(response)
            separator = Text.from_markup(
                "[yellow]───────────────────────────────────[/yellow]"
            )
            console.print(separator)
            console.print(Text.from_markup(
                f"[yellow]Extracted command:[/] "
                f"[bold]{extracted_cmd}[/bold]"
            ))
            run_prompt = Prompt.ask(
                Text.from_markup(
                    "[yellow]Execute? [/][green]y[/green]/[red]n[/red]"
                ),
                choices=["y", "n"], default="n"
            )
            if run_prompt.lower() == 'y':
                console.print(separator)
                self.run_command(extracted_cmd)
            else:
                console.print("[yellow]Command not executed.[/yellow]")


async def async_main(argv: List[str] = None):  # Added type hint for argv
    if argv is None:  # pragma: no cover
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        description="CL AI - Get bash commands from AI"  # Renamed
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
        cl_ai_instance.configure()
    elif args.list:
        cl_ai_instance.list_conversations()
    elif args.show:
        cl_ai_instance.show_conversation(args.show)
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


def main():  # pragma: no cover
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
