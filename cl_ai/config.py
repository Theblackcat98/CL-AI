import json
import os
from typing import Dict, Any

# Simple config
DEFAULT_CONFIG = {
    "model": "phi4:latest",
    "url": "http://localhost:11434/api",
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

CONFIG_FILE = os.path.expanduser("~/.cl_ai_config.json")
CONVERSATIONS_FILE = os.path.expanduser("~/.cl_ai_conversations.json")

def load_config(console) -> Dict[str, Any]:
    """Load config from file or use defaults."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config_data = json.load(f)
                if not isinstance(config_data, dict):
                    console.print(
                        f"[red]Error: Config file ({CONFIG_FILE}) "
                        f"does not contain a valid JSON object. Using "
                        f"default configuration.[/red]"
                    )
                    return DEFAULT_CONFIG
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
        except Exception as e:
            console.print(
                f"[red]Unexpected error loading config file "
                f"({CONFIG_FILE}): {e}. Using default "
                f"configuration.[/red]"
            )
            return DEFAULT_CONFIG

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
        return DEFAULT_CONFIG
    except Exception as e:
        console.print(
            f"[red]Unexpected error saving default config file "
            f"({CONFIG_FILE}): {e}. Using in-memory default "
            f"configuration for this session.[/red]"
        )
        return DEFAULT_CONFIG

def load_conversations(console) -> Dict[str, Any]:
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

def save_conversations(conversations, console):
    """Save conversations to file."""
    try:
        with open(CONVERSATIONS_FILE, "w") as f:
            json.dump(conversations, f, indent=2)
    except PermissionError as e:
        console.print(
            f"[red]Error saving conversations to {CONVERSATIONS_FILE}: {e}[/red]"
        )
    except Exception as e:
        console.print(
            f"[red]Unexpected error saving conversations: {e}[/red]"
        )

def save_config(config, console):
    """Save config to file."""
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        console.print("[green]Configuration saved.[/green]")
    except PermissionError as e:
        err_msg = (f"[red]Error saving configuration to "
                   f"{CONFIG_FILE}: {e}[/red]")
        console.print(err_msg)
    except Exception as e:
        console.print(
            f"[red]Unexpected error saving configuration: {e}[/red]"
        )
