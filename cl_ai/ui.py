from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

console = Console()

def show_help(config, console=console):
    """Show help information."""
    help_items = [
        "This tool helps you find the right bash commands by asking an "
        "AI.\n",
        "[bold]Available commands:[/bold]",
        "  [boldmagenta]!config[/boldmagenta]  - Configure CL AI",
        "  [boldmagenta]!help[/boldmagenta]   - Show this help",
        "  [boldmagenta]!history[/boldmagenta] - Show command history",
        "  [boldmagenta]!clear[/boldmagenta]  - Clear command history",
        "  [boldmagenta]!quit[/boldmagenta]   - Exit CL AI\n",
        "Or just type your question about a bash command and press "
        "Enter.\n"
    ]
    help_text_content = "\n".join(help_items)
    help_text = Text.from_markup(help_text_content)

    auto_run = config.get("auto_run_prompt", True)
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
            help_text, title="[cyan]CL AI Help[/cyan]",
            expand=False
        )
    )

def list_conversations(conversations, console=console):
    """List all conversations."""
    if not conversations:
        console.print("[yellow]No conversations found.[/yellow]")
        return

    table = Table(title="[cyan]Conversations[/cyan]")
    table.add_column("ID", style="dim", width=10)
    table.add_column("Title", style="green")

    for conv_id, conv_data in conversations.items():
        table.add_row(conv_id, conv_data["title"])

    console.print(table)

def show_conversation(conversations, identifier: str, find_conversation_func, console=console):
    """Show a conversation by title or ID."""
    conv_id = find_conversation_func(identifier)
    if not conv_id:
        console.print(f"[red]Conversation '{identifier}' not found.[/red]")
        return

    conv_data = conversations[conv_id]
    table = Table(title=f"Conversation: {conv_data['title']} ({conv_id})")
    table.add_column("Role", style="dim", width=10)
    table.add_column("Message", style="green")

    for message in conv_data["messages"]:
        table.add_row(message["role"], message["content"])

    console.print(table)

def configure_interactive(config, save_callback, console=console):
    """Configure the tool interactively."""
    run_prompt_status = config.get('auto_run_prompt', True)
    run_prompt_text = 'Enabled' if run_prompt_status else 'Disabled'
    prompt_display_limit = 50
    prompt_preview = config['prompt_prefix'][:prompt_display_limit]
    if len(config['prompt_prefix']) > prompt_display_limit:
        prompt_preview += "..."

    panel_content = (
        f"Current model: [bold]{config['model']}[/bold]\n"
        f"Current API URL: [bold]{config['url']}[/bold]\n"
        f"Run command prompt: [bold]{run_prompt_text}[/bold]\n"
        f"Current prompt: [bold]{prompt_preview}[/bold]"
    )
    console.print(Panel(
        Text.from_markup(panel_content),
        title="[cyan]CL AI Configuration[/cyan]",
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
            "Enter new model name", default=config["model"]
        )
        if new_model != config["model"]:
            config["model"] = new_model
            made_change = True
    elif choice == "2":
        new_url = Prompt.ask(
            "Enter new API URL", default=config["url"]
        )
        if new_url != config["url"]:
            config["url"] = new_url
            made_change = True
    elif choice == "3":
        console.print(Text.from_markup(
            f"\nCurrent prompt prefix:\n"
            f"[italic]{config['prompt_prefix']}[/italic]"
        ))
        new_prefix = Prompt.ask(
            "Enter new prompt prefix",
            default=config["prompt_prefix"]
        )
        if new_prefix != config["prompt_prefix"]:
            config["prompt_prefix"] = new_prefix
            made_change = True
    elif choice == "4":
        current_auto_run = config.get("auto_run_prompt", True)
        config["auto_run_prompt"] = not current_auto_run
        status_msg = ('disabled' if current_auto_run else 'enabled')
        console.print(
            f"[green]Run command prompt {status_msg}.[/green]"
        )
        made_change = True
    elif choice == "5":
        pass
    else:
        console.print(
            "[red]Invalid choice. Configuration not saved.[/red]"
        )
        return

    if made_change or choice == "5":
        save_callback(config)
    elif not made_change:
        console.print("[yellow]No changes made to configuration.[/yellow]")
