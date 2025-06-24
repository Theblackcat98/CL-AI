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
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

import re  # For extract_command

# Simple config
DEFAULT_CONFIG = {
    "model": "phi4:latest",  # Or your preferred default model
    "url": "http://localhost:11434/api",  # Adjust if your Ollama runs elsewhere
    "type": "ollama",
    "prompt_prefix": (
        "You are a helpful assistant that provides accurate bash commands for Linux. "
        "ONLY output the command. The command MUST be enclosed in a bash markdown code block "
        "(e.g., ```bash\\ncommand --option\\n```). "
        "Do NOT provide any explanation or any other text outside the code block unless explicitly asked. "
        "If you cannot provide a command, explain why in plain text without any code blocks."
    ),
    "auto_run_prompt": True
}

CONFIG_FILE = os.path.expanduser("~/.cmd_ai_config.json")
HISTORY_FILE = os.path.expanduser("~/.cmd_ai_history.json")

console = Console()


class CommandAI:
    def __init__(self):
        self.config = self.load_config()
        self.history = self.load_history()

    def load_config(self) -> Dict[str, Any]:
        """Load config from file or use defaults."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config_data = json.load(f)
                    # Basic validation: check if it's a dictionary
                    if not isinstance(config_data, dict):
                        console.print(f"[red]Error: Config file ({CONFIG_FILE}) does not contain a valid JSON object. Using default configuration.[/red]")
                        return DEFAULT_CONFIG
                    # You could add more specific key checks here if needed
                    return config_data
            except json.JSONDecodeError as e:
                console.print(f"[red]Error decoding config file ({CONFIG_FILE}): {e}. Using default configuration.[/red]")
                return DEFAULT_CONFIG
            except PermissionError as e:
                console.print(f"[red]Permission error reading config file ({CONFIG_FILE}): {e}. Using default configuration.[/red]")
                return DEFAULT_CONFIG
            except Exception as e:  # Catch any other unexpected errors
                console.print(f"[red]Unexpected error loading config file ({CONFIG_FILE}): {e}. Using default configuration.[/red]")
                return DEFAULT_CONFIG

        # Config file does not exist, create it with default settings
        console.print(
            f"[yellow]Config file not found at {CONFIG_FILE}. Creating with default settings.[/yellow]"
        )
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(DEFAULT_CONFIG, f, indent=2)
            return DEFAULT_CONFIG
        except PermissionError as e:
            console.print(
                f"[red]Permission error writing default config file ({CONFIG_FILE}): {e}. "
                f"Using in-memory default configuration for this session.[/red]"
            )
            return DEFAULT_CONFIG  # Return default config in memory
        except Exception as e:
            console.print(
                f"[red]Unexpected error saving default config file ({CONFIG_FILE}): {e}. "
                f"Using in-memory default configuration for this session.[/red]"
            )
            return DEFAULT_CONFIG

    def load_history(self) -> List[Dict[str, str]]:
        """Load chat history from file"""
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r") as f:
                    history_data = json.load(f)
                    # Basic validation: check if it's a list
                    if not isinstance(history_data, list):
                        console.print(
                            f"[yellow]Warning: History file ({HISTORY_FILE}) does not contain a valid JSON list. "
                            f"Starting with empty history.[/yellow]"
                        )
                        return []
                    # You could add further validation for list item structure if needed
                    return history_data
            except json.JSONDecodeError as e:
                console.print(
                    f"[yellow]Warning: Error decoding history file ({HISTORY_FILE}): {e}. "
                    f"Starting with empty history.[/yellow]"
                )
                return []
            except PermissionError as e:
                console.print(
                    f"[yellow]Warning: Permission error reading history file ({HISTORY_FILE}): {e}. "
                    f"Starting with empty history.[/yellow]"
                )
                return []
            except Exception as e:  # Catch any other unexpected errors
                console.print(
                    f"[yellow]Warning: Unexpected error loading history file ({HISTORY_FILE}): {e}. "
                    f"Starting with empty history.[/yellow]"
                )
                return []
        return []

    def save_history(self):
        """Save chat history to file"""
        # Keep only the last 20 interactions
        history_to_save = self.history[-20:] if len(self.history) > 20 else self.history
        with open(HISTORY_FILE, "w") as f:
            json.dump(history_to_save, f, indent=2)

    async def query_llm(self, prompt: str) -> str:
        """Query the LLM for a response"""
        messages = []

        # Add system message with prefix
        messages.append({
            "role": "system",
            "content": self.config["prompt_prefix"]
        })

        # Add past conversation for context (up to 5 exchanges)
        for item in self.history[-5:]:
            messages.append({"role": "user", "content": item["query"]})
            messages.append({"role": "assistant", "content": item["response"]})

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

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
            ) as progress:
                progress.add_task(description="Thinking...", total=None)
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(f"{self.config['url']}/chat", json=payload) as response:
                            if response.status != 200:
                                error_text = await response.text()
                                return f"Error: HTTP {response.status} - {error_text}"

                            result = await response.json()
                            response_text = result.get("message", {}).get("content", "No response")
                            return response_text

                except aiohttp.ClientError as e:
                    return f"Connection error: {str(e)}"
                except Exception as e:
                    return f"Error: {str(e)}"
        else:
            return "Only Ollama is supported currently."

    def configure(self):
        """Configure the tool interactively"""
        run_prompt_status = self.config.get('auto_run_prompt', True)
        run_prompt_text = 'Enabled' if run_prompt_status else 'Disabled'

        panel_content = (
            f"Current model: [bold]{self.config['model']}[/bold]\n"
            f"Current API URL: [bold]{self.config['url']}[/bold]\n"
            f"Run command prompt: [bold]{run_prompt_text}[/bold]\n"
            f"Current prompt: [bold]{self.config['prompt_prefix'][:50]}...[/bold]"
        )
        console.print(Panel(
            Text.from_markup(panel_content),
            title="[cyan]Command AI Configuration[/cyan]",
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
        choice = Prompt.ask("\nEnter your choice (1-5)", default="5", show_default=False)

        made_change = False
        if choice == "1":
            new_model = Prompt.ask("Enter new model name", default=self.config["model"])
            if new_model != self.config["model"]:
                self.config["model"] = new_model
                made_change = True
        elif choice == "2":
            new_url = Prompt.ask("Enter new API URL", default=self.config["url"])
            if new_url != self.config["url"]:
                self.config["url"] = new_url
                made_change = True
        elif choice == "3":
            console.print(Text.from_markup(
                f"\nCurrent prompt prefix:\n[italic]{self.config['prompt_prefix']}[/italic]"
            ))
            new_prefix = Prompt.ask("Enter new prompt prefix", default=self.config["prompt_prefix"])
            if new_prefix != self.config["prompt_prefix"]:
                self.config["prompt_prefix"] = new_prefix
                made_change = True
        elif choice == "4":
            current_auto_run = self.config.get("auto_run_prompt", True)
            self.config["auto_run_prompt"] = not current_auto_run
            console.print(
                f"[green]Run command prompt {'disabled' if current_auto_run else 'enabled'}.[/green]"
            )
            made_change = True  # Toggling is always a change
        elif choice == "5":
            # Save and exit, user might want to ensure the current state is written.
            pass
        else:
            console.print("[red]Invalid choice. Configuration not saved.[/red]")
            return  # Exit without saving for invalid choice

        if made_change or choice == "5":
            try:
                with open(CONFIG_FILE, "w") as f:
                    json.dump(self.config, f, indent=2)
                console.print("[green]Configuration saved.[/green]")
            except PermissionError as e:
                console.print(f"[red]Error saving configuration to {CONFIG_FILE}: {e}[/red]")
            except Exception as e:
                console.print(f"[red]Unexpected error saving configuration: {e}[/red]")
        elif not made_change:
            console.print("[yellow]No changes made to configuration.[/yellow]")

    def show_help(self):
        """Show help information"""
        help_items = [
            "This tool helps you find the right bash commands by asking an AI.\n",
            "[bold]Available commands:[/bold]",
            "  [boldmagenta]!config[/boldmagenta]  - Configure the tool",
            "  [boldmagenta]!help[/boldmagenta]   - Show this help",
            "  [boldmagenta]!history[/boldmagenta] - Show command history",
            "  [boldmagenta]!clear[/boldmagenta]  - Clear command history",
            "  [boldmagenta]!quit[/boldmagenta]   - Exit the tool\n",
            "Or just type your question about a bash command and press Enter.\n"
        ]
        help_text = Text.from_markup("\n".join(help_items))

        auto_run = self.config.get("auto_run_prompt", True)
        status_color = "green" if auto_run else "red"
        status_text_str = (
            f"\nCommand execution prompt is currently [{status_color}]"
            f"{'' if auto_run else 'not '}enabled[/{status_color}]."
        )
        help_text.append(Text.from_markup(status_text_str))
        help_text.append(Text.from_markup(
            "\nWhen enabled, you'll be asked whether to run each command after receiving it."
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

        console.print(Panel(help_text, title="[cyan]Command AI Help[/cyan]", expand=False))

    def show_history(self):
        """Show command history"""
        if not self.history:
            console.print("[yellow]No command history found.[/yellow]")
            return

        table = Table(title="[cyan]Command History[/cyan]")
        table.add_column("ID", style="dim", width=3)
        table.add_column("Query", style="green")
        table.add_column("Response", style="blue")

        for i, entry in enumerate(self.history[-10:], 1):
            table.add_row(str(i), entry['query'], entry['response'])

        console.print(table)

    def extract_command(self, response: str) -> str:
        """
        Extract the command from the LLM response text.
        Prioritizes bash code blocks, then generic code blocks.
        As a fallback, returns the first non-empty line if no code block is found,
        or the entire stripped response if it's a single line.
        """
        # Attempt to find a bash code block
        bash_match = re.search(r'```bash\s*(.*?)\s*```', response, re.DOTALL | re.IGNORECASE)
        if bash_match:
            return bash_match.group(1).strip()

        # If no bash block, attempt to find a generic code block
        generic_match = re.search(r'```\s*(.*?)\s*```', response, re.DOTALL)
        if generic_match:
            return generic_match.group(1).strip()

        # Fallback strategy:
        # If the LLM failed to provide a code block, but the prompt asks it to ONLY output the command,
        # the response might be the command itself, possibly with leading/trailing newlines.
        lines = [line for line in response.split('\n') if line.strip()]
        if len(lines) == 1:  # If it's a single line of text, assume it's the command
            return lines[0].strip()
        elif lines:  # If multiple lines, and no code block, this is ambiguous.
            # The new prompt tries to prevent this. For now, return first non-empty line.
            # Or, could return the whole thing if it's likely a multi-line command not in a block.
            # Current new prompt makes this less likely.
            console.print(
                "[yellow]Warning: LLM response contained multiple lines without a code block. "
                "Extracting the first non-empty line.[/yellow]"
            )
            return lines[0].strip()

        # If response is empty or only whitespace after all checks
        return response.strip()

    def run_command(self, command: str) -> None:
        """Run a command in the shell"""
        try:
            console.print(f"[yellow]Executing: [bold]{command}[/bold][/yellow]")
            # Using subprocess.run for better security and control
            result = subprocess.run(
                command, shell=True, check=False, text=True, capture_output=True
            )
            if result.stdout:
                console.print(Text(result.stdout.strip()))
            if result.stderr:
                console.print(Text(f"[red]Error output:[/red]\n{result.stderr.strip()}"))
            if result.returncode != 0:
                console.print(f"[red]Command failed with exit code {result.returncode}[/red]")
        except Exception as e:
            console.print(f"[red]Error executing command: {e}[/red]")

    async def process_command(self, command_str: str):  # Renamed command to command_str for clarity
        """Process a user command"""
        command_str = command_str.strip()

        if not command_str:
            return

        if command_str == "!help":
            self.show_help()
        elif command_str == "!config":
            self.configure()
        elif command_str == "!history":
            self.show_history()
        elif command_str == "!clear":
            self.history = []
            self.save_history()
            console.print("[green]History cleared.[/green]")
        elif command_str == "!quit":
            console.print("[green]Goodbye![/green]")
            return False
        else:
            # Query LLM
            response = await self.query_llm(command_str)

            # Print response
            console.print(f"\n[blue]{response}[/blue]\n")

            # Add to history
            self.history.append({
                "query": command_str,
                "response": response
            })

            # Save history
            self.save_history()

            # Prompt to run the command if auto_run_prompt is enabled
            if self.config.get("auto_run_prompt", True):
                extracted_cmd = self.extract_command(response)
                console.print(Text.from_markup(
                    "[yellow]───────────────────────────────────────────[/yellow]"
                ))
                console.print(Text.from_markup(
                    f"[yellow]Extracted command:[/] [bold]{extracted_cmd}[/bold]"
                ))
                run_prompt = Prompt.ask(
                    Text.from_markup("[yellow]Execute? [/][green]y[/green]/[red]n[/red]"),
                    choices=["y", "n"],
                    default="n"
                )
                if run_prompt.lower() == 'y':
                    console.print(Text.from_markup(
                        "[yellow]───────────────────────────────────────────[/yellow]"
                    ))
                    self.run_command(extracted_cmd)
                else:
                    console.print("[yellow]Command not executed.[/yellow]")

        return True

    async def interactive_mode(self):
        """Run in interactive mode"""
        # Set up readline history
        readline_history_path = os.path.expanduser("~/.cmd_ai_readline_history")
        if os.path.exists(readline_history_path):
            readline.read_history_file(readline_history_path)

        welcome_message = (
            f"Command AI - Ask for bash commands (type !help for help)\n"
            f"Using model: [bold]{self.config['model']}[/bold]"
        )
        console.print(Panel(Text.from_markup(welcome_message), title="[cyan]Welcome[/cyan]", expand=False))

        running = True
        while running:
            try:
                command_input = Prompt.ask(Text.from_markup("[green]cmd-ai>[/green]"))
                running = await self.process_command(command_input)  # Corrected variable
            except KeyboardInterrupt:
                console.print("\nExiting...")
                break
            except EOFError:
                console.print("\nExiting...")
                break

        # Save readline history
        readline.write_history_file(readline_history_path)

    async def one_shot_mode(self, query: str):
        """Run in one-shot mode for a single query"""
        response = await self.query_llm(query)
        console.print(f"\n[blue]{response}[/blue]\n")

        # Add to history
        self.history.append({
            "query": query,
            "response": response
        })

        # Save history
        self.save_history()

        # Prompt to run the command if auto_run_prompt is enabled
        if self.config.get("auto_run_prompt", True):
            extracted_cmd = self.extract_command(response)
            console.print(Text.from_markup(
                "[yellow]───────────────────────────────────────────[/yellow]"
            ))
            console.print(Text.from_markup(
                f"[yellow]Extracted command:[/] [bold]{extracted_cmd}[/bold]"
            ))
            run_prompt = Prompt.ask(
                Text.from_markup("[yellow]Execute? [/][green]y[/green]/[red]n[/red]"),
                choices=["y", "n"],
                default="n"
            )
            if run_prompt.lower() == 'y':
                console.print(Text.from_markup(
                    "[yellow]───────────────────────────────────────────[/yellow]"
                ))
                self.run_command(extracted_cmd)
            else:
                console.print("[yellow]Command not executed.[/yellow]")


async def async_main(argv=None):  # Added argv for easier testing
    if argv is None:  # pragma: no cover
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(
        description="Command AI - Get bash commands from AI"
    )
    parser.add_argument(
        "query", nargs="*", help="Query to send to the AI (omit for interactive mode)"
    )
    parser.add_argument(
        "--config", action="store_true", help="Configure the tool"
    )
    parser.add_argument(
        "--history", action="store_true", help="Show command history"
    )

    args = parser.parse_args(argv)  # Use argv here
    cmd_ai_instance = CommandAI()  # Renamed for clarity

    if args.config:
        cmd_ai_instance.configure()
    elif args.history:
        cmd_ai_instance.show_history()
    elif args.query:
        query_str = " ".join(args.query)
        await cmd_ai_instance.one_shot_mode(query_str)
    else:
        await cmd_ai_instance.interactive_mode()


def main():  # pragma: no cover
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
