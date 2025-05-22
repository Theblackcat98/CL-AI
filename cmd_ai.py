#!/usr/bin/env python3

import json
import os
import sys
import asyncio
import aiohttp
from typing import Dict, List, Any, Optional
import argparse
import readline  # For command history

# Simple config
DEFAULT_CONFIG = {
    "model": "phi4:latest",
    "url": "http://localhost:11434/api",
    "type": "ollama",
    "prompt_prefix": "You are a helpful assistant that provides accurate bash commands for Linux. Be concise and only output the command, unless the user specifically asks for explanation.",
    "auto_run_prompt": True  # New setting to toggle the run command prompt
}

CONFIG_FILE = os.path.expanduser("~/.cmd_ai_config.json")
HISTORY_FILE = os.path.expanduser("~/.cmd_ai_history.json")

class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[32m"
    BLUE = "\033[34m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    CYAN = "\033[36m"
    MAGENTA = "\033[35m"

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
                print(f"{Colors.RED}Error loading config: {e}{Colors.RESET}")
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
    
    def show_spinner(self, message="Thinking"):
        """Show a spinner while the LLM is processing"""
        spinner_chars = "|/-\\"
        i = 0
        
        def spin():
            nonlocal i
            sys.stdout.write(f"\r{Colors.YELLOW}{spinner_chars[i % len(spinner_chars)]} {message}...{Colors.RESET}")
            sys.stdout.flush()
            i += 1
            
        return spin
            
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
            
            # Start spinner in a separate thread
            spinner = self.show_spinner()
            spinner_task = asyncio.create_task(self._run_spinner(spinner))
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(f"{self.config['url']}/chat", json=payload) as response:
                        # Cancel spinner
                        spinner_task.cancel()
                        sys.stdout.write("\r" + " " * 50 + "\r")  # Clear spinner line
                        
                        if response.status != 200:
                            error_text = await response.text()
                            return f"Error: HTTP {response.status} - {error_text}"
                        
                        result = await response.json()
                        response_text = result.get("message", {}).get("content", "No response")
                        return response_text
                        
            except aiohttp.ClientError as e:
                spinner_task.cancel()
                sys.stdout.write("\r" + " " * 50 + "\r")  # Clear spinner line
                return f"Connection error: {str(e)}"
            except Exception as e:
                spinner_task.cancel()
                sys.stdout.write("\r" + " " * 50 + "\r")  # Clear spinner line
                return f"Error: {str(e)}"
        else:
            return "Only Ollama is supported currently."
            
    async def _run_spinner(self, spinner_func):
        """Run the spinner animation"""
        while True:
            spinner_func()
            await asyncio.sleep(0.1)
            
    def configure(self):
        """Configure the tool interactively"""
        print(f"\n{Colors.CYAN}===== Command AI Configuration ====={Colors.RESET}")
        print(f"Current model: {Colors.BOLD}{self.config['model']}{Colors.RESET}")
        print(f"Current API URL: {Colors.BOLD}{self.config['url']}{Colors.RESET}")
        print(f"Run command prompt: {Colors.BOLD}{'Enabled' if self.config.get('auto_run_prompt', True) else 'Disabled'}{Colors.RESET}")
        print(f"Current prompt: {Colors.BOLD}{self.config['prompt_prefix'][:50]}...{Colors.RESET}")
        
        print("\nWhat would you like to change?")
        print("1. Model name")
        print("2. API URL")
        print("3. Prompt prefix")
        print("4. Toggle run command prompt")
        print("5. Save and exit")
        
        choice = input("\nEnter your choice (1-5): ")
        
        if choice == "1":
            model = input("Enter new model name: ")
            if model:
                self.config["model"] = model
        elif choice == "2":
            url = input("Enter new API URL: ")
            if url:
                self.config["url"] = url
        elif choice == "3":
            print("\nCurrent prompt prefix:")
            print(self.config["prompt_prefix"])
            prefix = input("\nEnter new prompt prefix: ")
            if prefix:
                self.config["prompt_prefix"] = prefix
        elif choice == "4":
            # Toggle the auto_run_prompt setting
            current = self.config.get("auto_run_prompt", True)
            self.config["auto_run_prompt"] = not current
            print(f"{Colors.GREEN}Run command prompt {'disabled' if current else 'enabled'}.{Colors.RESET}")
        elif choice == "5" or choice == "":
            pass
        else:
            print(f"{Colors.RED}Invalid choice{Colors.RESET}")
            
        # Save config to file
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=2)
        print(f"{Colors.GREEN}Configuration saved{Colors.RESET}")
            
    def show_help(self):
        """Show help information"""
        print(f"\n{Colors.CYAN}===== Command AI Help ====={Colors.RESET}")
        print("This tool helps you find the right bash commands by asking an AI.")
        print("\nAvailable commands:")
        print(f"  {Colors.BOLD}!config{Colors.RESET} - Configure the tool")
        print(f"  {Colors.BOLD}!help{Colors.RESET} - Show this help")
        print(f"  {Colors.BOLD}!history{Colors.RESET} - Show command history")
        print(f"  {Colors.BOLD}!clear{Colors.RESET} - Clear command history")
        print(f"  {Colors.BOLD}!quit{Colors.RESET} - Exit the tool")
        print("\nOr just type your question about a bash command and press Enter.")
        
        # Show command execution status
        auto_run = self.config.get("auto_run_prompt", True)
        print(f"\nCommand execution prompt is currently {Colors.GREEN if auto_run else Colors.RED}{'' if auto_run else 'not '}enabled{Colors.RESET}.")
        print("When enabled, you'll be asked whether to run each command after receiving it.")
        print("You can toggle this feature in the configuration menu (!config).")
        
        print("\nExamples:")
        print("  How do I find files modified in the last 24 hours?")
        print("  What's the command to check disk space usage?")
        print("  How can I extract a tar.gz file?")
        
    def show_history(self):
        """Show command history"""
        if not self.history:
            print(f"{Colors.YELLOW}No command history found.{Colors.RESET}")
            return
            
        print(f"\n{Colors.CYAN}===== Command History ====={Colors.RESET}")
        for i, entry in enumerate(self.history[-10:], 1):
            print(f"{i}. {Colors.GREEN}Q: {entry['query']}{Colors.RESET}")
            print(f"   {Colors.BLUE}A: {entry['response']}{Colors.RESET}")
            print()
            
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
        command_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Skip likely explanation lines
            if line.lower().startswith(('to ', 'this ', 'you ', 'the ', 'here', 'use ', 'if ', 'note:', 'note that')):
                continue
            
            # Skip markdown headings
            if line.startswith('#'):
                continue
            
            # Skip lines that are too long (likely explanations)
            if len(line) > 100 and ' ' in line.strip():
                continue
            
            # Skip lines with too many punctuation marks (likely explanations)
            if line.count('.') > 2 or line.count(',') > 2:
                continue
            
            # Keep lines that look like commands
            if (' | ' in line or ';' in line or '>' in line or 
                line.startswith('$') or line.startswith('sudo') or
                line.startswith('./') or line.startswith('find') or
                line.startswith('grep') or line.startswith('ls') or
                line.startswith('cat') or line.startswith('cd')):
                # If line starts with $, remove it
                if line.startswith('$'):
                    line = line[1:].strip()
                command_lines.append(line)
            
        # If we found command-like lines, use the first one
        if command_lines:
            return command_lines[0]
        
        # If no clear command line found, use the first non-empty line as a last resort
        for line in lines:
            if line.strip():
                return line.strip()
        
        # If all else fails, return the whole response
        return response.strip()

    def run_command(self, command: str) -> None:
        """Run a command in the shell"""
        try:
            print(f"{Colors.YELLOW}Executing: {Colors.BOLD}{command}{Colors.RESET}")
            os.system(command)
        except Exception as e:
            print(f"{Colors.RED}Error executing command: {e}{Colors.RESET}")

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
            print(f"{Colors.GREEN}History cleared.{Colors.RESET}")
        elif command == "!quit":
            print(f"{Colors.GREEN}Goodbye!{Colors.RESET}")
            return False
        else:
            # Query LLM
            response = await self.query_llm(command)
            
            # Print response
            print(f"\n{Colors.BLUE}{response}{Colors.RESET}\n")
            
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
                print(f"{Colors.YELLOW}───────────────────────────────────────────{Colors.RESET}")
                print(f"{Colors.YELLOW}Extracted command:{Colors.RESET} {Colors.BOLD}{cmd}{Colors.RESET}")
                run_prompt = input(f"{Colors.YELLOW}Execute? {Colors.RESET}[{Colors.GREEN}y{Colors.RESET}/{Colors.RED}n{Colors.RESET}]: ")
                if run_prompt.lower() in ('y', 'yes'):
                    print(f"{Colors.YELLOW}───────────────────────────────────────────{Colors.RESET}")
                    self.run_command(cmd)
                else:
                    print(f"{Colors.YELLOW}Command not executed.{Colors.RESET}")
        
        return True
            
    async def interactive_mode(self):
        """Run in interactive mode"""
        # Set up readline history
        if os.path.exists(os.path.expanduser("~/.cmd_ai_readline_history")):
            readline.read_history_file(os.path.expanduser("~/.cmd_ai_readline_history"))
            
        print(f"{Colors.CYAN}Command AI - Ask for bash commands (type !help for help){Colors.RESET}")
        print(f"Using model: {Colors.BOLD}{self.config['model']}{Colors.RESET}")
        
        running = True
        while running:
            try:
                command = input(f"{Colors.GREEN}cmd-ai>{Colors.RESET} ")
                running = await self.process_command(command)
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except EOFError:
                print("\nExiting...")
                break
                
        # Save readline history
        readline.write_history_file(os.path.expanduser("~/.cmd_ai_readline_history"))
        
    async def one_shot_mode(self, query: str):
        """Run in one-shot mode for a single query"""
        response = await self.query_llm(query)
        print(f"\n{Colors.BLUE}{response}{Colors.RESET}\n")
        
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
            print(f"{Colors.YELLOW}───────────────────────────────────────────{Colors.RESET}")
            print(f"{Colors.YELLOW}Extracted command:{Colors.RESET} {Colors.BOLD}{cmd}{Colors.RESET}")
            run_prompt = input(f"{Colors.YELLOW}Execute? {Colors.RESET}[{Colors.GREEN}y{Colors.RESET}/{Colors.RED}n{Colors.RESET}]: ")
            if run_prompt.lower() in ('y', 'yes'):
                print(f"{Colors.YELLOW}───────────────────────────────────────────{Colors.RESET}")
                self.run_command(cmd)
            else:
                print(f"{Colors.YELLOW}Command not executed.{Colors.RESET}")

async def main():
    parser = argparse.ArgumentParser(description="Command AI - Get bash commands from AI")
    parser.add_argument("query", nargs="*", help="Query to send to the AI (omit for interactive mode)")
    parser.add_argument("--config", action="store_true", help="Configure the tool")
    parser.add_argument("--history", action="store_true", help="Show command history")
    
    args = parser.parse_args()
    cmd_ai = CommandAI()
    
    if args.config:
        cmd_ai.configure()
    elif args.history:
        cmd_ai.show_history()
    elif args.query:
        query = " ".join(args.query)
        await cmd_ai.one_shot_mode(query)
    else:
        await cmd_ai.interactive_mode()

if __name__ == "__main__":
    asyncio.run(main()) 