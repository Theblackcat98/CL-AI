#!/usr/bin/env python3

import json
import os
import sys
import asyncio
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

# Simple config
DEFAULT_CONFIG = {
    "model": "phi4:latest",
    "url": "http://localhost:11434/api",
    "type": "ollama",
    "prompt_prefix": (
        "You are a helpful assistant that provides accurate bash commands for Linux. "
        "Be concise and only output the command, unless the user specifically asks for explanation."
    ),
    "auto_run_prompt": True  # New setting to toggle the run command prompt
}

CONFIG_FILE = os.path.expanduser("~/.cmd_ai_config.json")
HISTORY_FILE = os.path.expanduser("~/.cmd_ai_history.json")

console = Console()


class CommandAI:
    def __init__(self):
        self.config = self.load_config()
        self.history = self.load_history()

    def load_config(self) -> Dict[str, Any]:
        """Load config from file or use defaults"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    return json.load(f)
            except Exception as e:
                console.print(f"[red]Error loading config: {e}[/red]")
                return DEFAULT_CONFIG
        else:
            # Save default config
            with open(CONFIG_FILE, "w") as f:
                json.dump(DEFAULT_CONFIG, f, indent=2)
            return DEFAULT_CONFIG

    def load_history(self) -> List[Dict[str, str]]:
        """Load chat history from file"""
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r") as f:
                    return json.load(f)
            except Exception:
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
        console.print(Panel(
            Text.from_markup(
                f"Current model: [bold]{self.config['model']}[/bold]\n"
                f"Current API URL: [bold]{self.config['url']}[/bold]\n"
                f"Run command prompt: [bold]{'Enabled' if self.config.get('auto_run_prompt', True) else 'Disabled'}[/bold]\n"
                f"Current prompt: [bold]{self.config['prompt_prefix'][:50]}...[/bold]"
            ),
            title="[cyan]Command AI Configuration[/cyan]",
            expand=False
        ))

        menu_text = Text.from_markup(
            "What would you like to change?\n"
            "  1. Model name\n"
            "  2. API URL\n"
            "  3. Prompt prefix\n"
            "  4. Toggle run command prompt\n"
            "  5. Save and exit"
        )
        console.print(menu_text)
        choice = Prompt.ask("\nEnter your choice (1-5)", default="5", show_default=False)

        if choice == "1":
            model = Prompt.ask("Enter new model name", default=self.config["model"])
            if model:
                self.config["model"] = model
        elif choice == "2":
            url = Prompt.ask("Enter new API URL", default=self.config["url"])
            if url:
                self.config["url"] = url
        elif choice == "3":
            console.print(Text.from_markup(f"\nCurrent prompt prefix:\n[italic]{self.config['prompt_prefix']}[/italic]"))
            prefix = Prompt.ask("Enter new prompt prefix", default=self.config["prompt_prefix"])
            if prefix:
                self.config["prompt_prefix"] = prefix
        elif choice == "4":
            current = self.config.get("auto_run_prompt", True)
            self.config["auto_run_prompt"] = not current
            console.print(f"[green]Run command prompt {'disabled' if current else 'enabled'}.[/green]")
        elif choice == "5":
            pass
        else:
            console.print("[red]Invalid choice[/red]")

        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=2)
        console.print("[green]Configuration saved[/green]")

    def show_help(self):
        """Show help information"""
        help_text = Text.from_markup(
            "This tool helps you find the right bash commands by asking an AI.\n\n"
            "[bold]Available commands:[/bold]\n"
            "  [boldmagenta]!config[/boldmagenta]  - Configure the tool\n"
            "  [boldmagenta]!help[/boldmagenta]   - Show this help\n"
            "  [boldmagenta]!history[/boldmagenta] - Show command history\n"
            "  [boldmagenta]!clear[/boldmagenta]  - Clear command history\n"
            "  [boldmagenta]!quit[/boldmagenta]   - Exit the tool\n\n"
            "Or just type your question about a bash command and press Enter.\n"
        )

        auto_run = self.config.get("auto_run_prompt", True)
        status_color = "green" if auto_run else "red"
        status_text = (
            f"\nCommand execution prompt is currently [{status_color}]{'' if auto_run else 'not '}enabled[/{status_color}]."
        )
        help_text.append(Text.from_markup(status_text))
        help_text.append(Text.from_markup("\nWhen enabled, you'll be asked whether to run each command after receiving it."))
        help_text.append(Text.from_markup("You can toggle this feature in the configuration menu (!config)."))

        help_text.append(Text.from_markup(
            "\n\n[bold]Examples:[/bold]\n"
            "  How do I find files modified in the last 24 hours?\n"
            "  What's the command to check disk space usage?\n"
            "  How can I extract a tar.gz file?"
        ))

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
        """Extract the command from the response text"""
        # Check if the response contains a markdown code block
        if '```' in response:
            # Extract content from code blocks (prioritize bash blocks)
            bash_pattern = r'```bash\s*(.*?)\s*```'
            generic_pattern = r'```\s*(.*?)\s*```'

            import re
            # First try to find bash-specific code blocks
            bash_matches = re.findall(bash_pattern, response, re.DOTALL)
            if bash_matches:
                # Return the first bash code block content
                return bash_matches[0].strip()

            # If no bash blocks, try generic code blocks
            generic_matches = re.findall(generic_pattern, response, re.DOTALL)
            if generic_matches:
                # Return the first code block content
                return generic_matches[0].strip()

        # If no code blocks or extraction failed, fall back to line-by-line analysis
        lines = response.split('\n')
        command_lines = []  # Lines that strongly look like commands
        candidate_lines = []  # Lines that are not obvious explanations

        for line_content in lines:
            line = line_content.strip()
            if not line:
                continue

            is_explanation = False
            # Skip likely explanation lines
            explan_prefixes = ('to ', 'this ', 'you ', 'the ', 'here', 'use ', 'if ', 'note:', 'note that', 'it ')
            if line.lower().startswith(explan_prefixes):
                is_explanation = True

            # Skip markdown headings
            if line.startswith('#'):
                is_explanation = True

            # Skip lines that are too long (likely explanations)
            # allow longer chained commands
            if len(line) > 120 and ' ' in line.strip() and not ('&&' in line or '||' in line):
                is_explanation = True

            # Skip lines with too many punctuation marks (likely explanations) unless they are part of a command structure
            # find/grep can have dots
            if (line.count('.') > 2 or line.count(',') > 2) and not ('find ' in line or 'grep ' in line):
                is_explanation = True

            if not is_explanation:
                candidate_lines.append(line)

            # Check for strong command indicators
            command_indicators = (' | ', ';', '>', '<', '&&', '||')
            command_prefixes = (
                '$', 'sudo', './', 'apt', 'git', 'docker', 'kubectl', 'find', 'grep', 'ls', 'cat', 'cd', 'mkdir',
                'rm', 'cp', 'mv', 'df', 'du', 'ps'
            )
            if any(ind in line for ind in command_indicators) or \
               any(line.startswith(pref) for pref in command_prefixes):
                processed_line = line[1:].strip() if line.startswith('$') else line
                command_lines.append(processed_line)

        # Prioritize lines identified by strong command indicators
        if command_lines:
            return command_lines[0]

        # If no strong command indicators, use the first candidate line (not an explanation)
        if candidate_lines:
            return candidate_lines[0]

        # If all lines seemed like explanations or were empty, fall back to the first non-empty line from original input
        for line_content in lines:
            if line_content.strip():
                return line_content.strip()

        # If all else fails (e.g., empty response), return the whole response stripped
        return response.strip()

    def run_command(self, command: str) -> None:
        """Run a command in the shell"""
        try:
            console.print(f"[yellow]Executing: [bold]{command}[/bold][/yellow]")
            os.system(command)
        except Exception as e:
            console.print(f"[red]Error executing command: {e}[/red]")

    async def process_command(self, command: str):
        """Process a user command"""
        command = command.strip()

        if not command:
            return

        if command == "!help":
            self.show_help()
        elif command == "!config":
            self.configure()
        elif command == "!history":
            self.show_history()
        elif command == "!clear":
            self.history = []
            self.save_history()
            console.print("[green]History cleared.[/green]")
        elif command == "!quit":
            console.print("[green]Goodbye![/green]")
            return False
        else:
            # Query LLM
            response = await self.query_llm(command)

            # Print response
            console.print(f"\n[blue]{response}[/blue]\n")

            # Add to history
            self.history.append({
                "query": command,
                "response": response
            })

            # Save history
            self.save_history()

            # Prompt to run the command if auto_run_prompt is enabled
            if self.config.get("auto_run_prompt", True):
                cmd = self.extract_command(response)
                console.print(Text.from_markup("[yellow]───────────────────────────────────────────[/yellow]"))
                console.print(Text.from_markup(f"[yellow]Extracted command:[/] [bold]{cmd}[/bold]"))
                run_prompt = Prompt.ask(
                    Text.from_markup("[yellow]Execute? [/][green]y[/green]/[red]n[/red]"),
                    choices=["y", "n"],
                    default="n"
                )
                if run_prompt.lower() == 'y':
                    console.print(Text.from_markup("[yellow]───────────────────────────────────────────[/yellow]"))
                    self.run_command(cmd)
                else:
                    console.print("[yellow]Command not executed.[/yellow]")

        return True

    async def interactive_mode(self):
        """Run in interactive mode"""
        # Set up readline history
        readline_history_path = os.path.expanduser("~/.cmd_ai_readline_history")
        if os.path.exists(readline_history_path):
            readline.read_history_file(readline_history_path)

        welcome_text = Text.from_markup(
            f"Command AI - Ask for bash commands (type !help for help)\nUsing model: [bold]{self.config['model']}[/bold]"
        )
        console.print(Panel(welcome_text, title="[cyan]Welcome[/cyan]", expand=False))

        running = True
        while running:
            try:
                command_input = Prompt.ask(Text.from_markup("[green]cmd-ai>[/green]"))  # Removed trailing space
                running = await self.process_command(command)
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
            cmd = self.extract_command(response)
            console.print(Text.from_markup("[yellow]───────────────────────────────────────────[/yellow]"))
            console.print(Text.from_markup(f"[yellow]Extracted command:[/] [bold]{cmd}[/bold]"))
            run_prompt = Prompt.ask(
                Text.from_markup("[yellow]Execute? [/][green]y[/green]/[red]n[/red]"),
                choices=["y", "n"],
                default="n"
            )
            if run_prompt.lower() == 'y':
                console.print(Text.from_markup("[yellow]───────────────────────────────────────────[/yellow]"))
                self.run_command(cmd)
            else:
                console.print("[yellow]Command not executed.[/yellow]")


async def async_main(argv=None):  # Added argv for easier testing
    if argv is None:  # pragma: no cover
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description="Command AI - Get bash commands from AI")
    parser.add_argument("query", nargs="*", help="Query to send to the AI (omit for interactive mode)")
    parser.add_argument("--config", action="store_true", help="Configure the tool")
    parser.add_argument("--history", action="store_true", help="Show command history")

    args = parser.parse_args(argv)  # Use argv here
    cmd_ai = CommandAI()

    if args.config:
        cmd_ai.configure()
    elif args.history:
        cmd_ai.show_history()
    elif args.query:
        query_str = " ".join(args.query)
        await cmd_ai.one_shot_mode(query_str)
    else:
        await cmd_ai.interactive_mode()


def main():  # pragma: no cover
    asyncio.run(async_main())


if __name__ == "__main__":
    main()