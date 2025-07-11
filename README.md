# CL-AI

A minimal command-line tool to get bash commands from local LLMs.

## Features

- Native command-line interface that preserves your terminal, with an improved Text User Interface (TUI) powered by the `rich` library.
- Works both interactively and as a one-shot command.
- Color-coded and well-formatted responses.
- Command history and configuration accessible via interactive commands or command-line arguments.
- Loading spinner for feedback during LLM queries.
- Connects to local LLMs like Ollama.
- Prompts to run commands directly (toggleable).

## Installation

This package will be installable via pip:
```bash
pip install cl-ai
```

Previously, to run directly from source:
```bash
# Make the script executable (if running from source)
# chmod +x cmd_ai.py

# Optional: create a symlink in your PATH (if running from source)
# ln -s $(pwd)/cmd_ai.py ~/.local/bin/cl-ai
```

## Usage

Once installed via pip, you can run `cl-ai` directly.

### Interactive Mode

Run the tool without arguments to enter interactive mode:

```bash
cl-ai
```

You'll get a prompt where you can type your queries:

```
cl-ai> How do I find large files in the current directory?
```

After receiving a response, the tool will ask if you want to run the command:

```
Run this command? [y/n] find . -type f -size +10M -exec ls -lh {} \;:
```

You can enable or disable this prompt in the configuration.

### One-Shot Mode

You can also use it directly from your terminal for a single query:

```bash
cl-ai "How do I find files modified in the last 24 hours?"
```

### Commands

In interactive mode, you can use these special commands:

- `!help` - Show help information
- `!config` - Configure CL AI
- `!history` - Show command history
- `!clear` - Clear command history
- `!quit` - Exit CL AI

### Command-Line Arguments

```bash
# Configure the tool
cl-ai --config

# Show command history
cl-ai --history

# Get help
cl-ai --help
```

## Configuration

Configuration is stored in `~/.cl_ai_config.json` and can be edited directly or
using the `!config` command in interactive mode or `--config` on the command line.

Configuration options:
- `model`: The LLM model to use (e.g., "phi4:latest")
- `url`: The API URL
- `type`: The API type (currently only "ollama")
- `prompt_prefix`: System prompt for the LLM
- `auto_run_prompt`: Whether to prompt to run commands (true/false)

## Running Tests

Unit tests are included to ensure functionality. To run the tests, navigate to the project directory and use the following command:

```bash
python -m unittest discover -v
```
This will automatically discover and run all tests in the `test_cmd_ai.py` file.
(Note: Test file name might need update if module name `cmd_ai.py` changes).

## Examples

```bash
# Get a command to find large files
cl-ai> How do I find files larger than 100MB?

# Get a command to monitor system resources
cl-ai> How can I monitor CPU and memory usage?

# One-shot mode
cl-ai "How do I search for text in multiple files?"
```