# cmd-ai

A minimal command-line tool to get bash commands from local LLMs.

## Features

- Native command-line interface that preserves your terminal
- Works both interactively and as a one-shot command
- Color-coded responses
- Command history and configuration
- Loading spinner for feedback
- Connects to local LLMs like Ollama
- Prompts to run commands directly (toggleable)

## Installation

```bash
# Make the script executable
chmod +x cmd_ai.py

# Optional: create a symlink in your PATH
ln -s $(pwd)/cmd_ai.py ~/.local/bin/cmd-ai
```

## Usage

### Interactive Mode

Run the tool without arguments to enter interactive mode:

```bash
./cmd_ai.py
```

You'll get a prompt where you can type your queries:

```
cmd-ai> How do I find large files in the current directory?
```

After receiving a response, the tool will ask if you want to run the command:

```
Run this command? [y/n] find . -type f -size +10M -exec ls -lh {} \;:
```

You can enable or disable this prompt in the configuration.

### One-Shot Mode

You can also use it directly from your terminal for a single query:

```bash
./cmd_ai.py "How do I find files modified in the last 24 hours?"
```

### Commands

In interactive mode, you can use these special commands:

- `!help` - Show help information
- `!config` - Configure the tool
- `!history` - Show command history
- `!clear` - Clear command history
- `!quit` - Exit interactive mode

### Command-Line Arguments

```bash
# Configure the tool
./cmd_ai.py --config

# Show command history
./cmd_ai.py --history

# Get help
./cmd_ai.py --help
```

## Configuration

Configuration is stored in `~/.cmd_ai_config.json` and can be edited directly or 
using the `!config` command in interactive mode or `--config` on the command line.

Configuration options:
- `model`: The LLM model to use (e.g., "phi4:latest")
- `url`: The API URL
- `type`: The API type (currently only "ollama")
- `prompt_prefix`: System prompt for the LLM
- `auto_run_prompt`: Whether to prompt to run commands (true/false)

## Examples

```bash
# Get a command to find large files
cmd-ai> How do I find files larger than 100MB?

# Get a command to monitor system resources
cmd-ai> How can I monitor CPU and memory usage?

# One-shot mode
./cmd_ai.py "How do I search for text in multiple files?"
``` 