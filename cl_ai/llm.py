import aiohttp
import re
import sys
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

async def query_llm(config, prompt: str, conversations: dict = None, conversation_id: str = None) -> str:
    """Query the LLM for a response."""
    messages = []

    # Add system message with prefix
    messages.append({
        "role": "system",
        "content": config["prompt_prefix"]
    })

    if conversation_id and conversations and conversation_id in conversations:
        for message in conversations[conversation_id]["messages"]:
            messages.append(message)

    # Add current prompt
    messages.append({
        "role": "user",
        "content": prompt
    })

    # Set up the API request
    if config["type"] == "ollama":
        payload = {
            "model": config["model"],
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
                    api_url = f"{config['url']}/chat"
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

def extract_command(response: str) -> str:
    """
    Extract the command from the LLM response text.
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
