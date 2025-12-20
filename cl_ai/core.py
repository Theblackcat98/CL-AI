import os
import sys
import subprocess
import readline
from rich.text import Text
from rich.prompt import Prompt
from rich.panel import Panel

from cl_ai.config import load_config, load_conversations, save_conversations, save_config
from cl_ai.ui import console, show_help, configure_interactive, list_conversations, show_conversation
from cl_ai.llm import query_llm, extract_command

class CLAI:
    def __init__(self):
        self.config = load_config(console)
        self.conversations = load_conversations(console)

    def save_conversations(self):
        save_conversations(self.conversations, console)

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
            show_help(self.config, console)
        elif command_str == "!config":
            configure_interactive(self.config, lambda c: save_config(c, console), console)
        elif command_str == "!history": # Added handling for history command
            list_conversations(self.conversations, console)
        elif command_str == "!clear": # Added handling for clear command
            self.conversations = {}
            self.save_conversations()
            console.print("[green]History cleared.[/green]")
        elif command_str == "!quit":
            console.print("[green]Goodbye![/green]")
            return False, conversation_id
        else:
            response = await query_llm(self.config, command_str, self.conversations, conversation_id)
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
                extracted_cmd = extract_command(response)
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
            "~/.cl_ai_readline_history"
        )
        if os.path.exists(readline_history_path):
            try:
                readline.read_history_file(readline_history_path)
            except Exception as e:  # Catch potential errors reading history
                console.print(
                    f"[yellow]Could not load readline history: {e}[/yellow]"
                )

        welcome_message_text = (
            f"CL AI - Ask for bash commands (type !help for help)\n"
            f"Using model: [bold]{self.config['model']}[/bold]"
        )
        console.print(
            Panel(
                Text.from_markup(welcome_message_text),
                title="[cyan]Welcome to CL AI[/cyan]",
                expand=False
            )
        )

        running = True
        conversation_id = None
        while running:
            try:
                prompt_text = Text.from_markup(
                    "[green]cl-ai>[/green]"
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

        response = await query_llm(self.config, query, self.conversations, conversation_id)
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
            extracted_cmd = extract_command(response)
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

    def delete_conversation(self, identifier: str):
        """Delete a conversation by title or ID."""
        conv_id = self.find_conversation(identifier)
        if not conv_id:
            console.print(f"[red]Conversation '{identifier}' not found.[/red]")
            return

        del self.conversations[conv_id]
        self.save_conversations()
        console.print(f"[green]Conversation '{identifier}' deleted.[/green]")

    def get_latest_conversation_id(self) -> str:
        """Get the ID of the most recent conversation."""
        if not self.conversations:
            return None
        return list(self.conversations.keys())[-1]
