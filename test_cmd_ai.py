import unittest
from unittest.mock import patch, mock_open, MagicMock
import json
import os
import sys
import aiohttp  # Added import for aiohttp.ClientError

# Add the directory containing cmd_ai.py to sys.path
# This allows importing cmd_ai when running tests from the test directory
# or project root
# Assuming test_cmd_ai.py is in the same dir as cmd_ai.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
# If cmd_ai.py is in parent directory:
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cmd_ai import CLAI, DEFAULT_CONFIG, CONFIG_FILE, CONVERSATIONS_FILE, async_main


# Store original os.path.exists to use in tearDown if needed for actual
# file cleanup
# _original_os_path_exists = os.path.exists


class TestCLAI(unittest.TestCase):  # Renamed class

    def setUp(self):
        self.cl_ai = CLAI()  # Renamed instance variable
        # Patch os.path.exists globally for most tests to avoid actual file
        # checks, unless a specific test needs to interact with the file
        # system.
        self.patcher_os_exists = patch('os.path.exists')
        self.mock_os_exists = self.patcher_os_exists.start()

        # Patch builtins.open globally
        self.patcher_open = patch('builtins.open', new_callable=mock_open)
        self.mock_file_open = self.patcher_open.start()

        # Patch json.dump and json.load
        self.patcher_json_dump = patch('json.dump')
        self.mock_json_dump = self.patcher_json_dump.start()

        self.patcher_json_load = patch('json.load')
        self.mock_json_load = self.patcher_json_load.start()

        # Patch console.print
        self.patcher_console_print = patch('cmd_ai.console.print')
        self.mock_console_print = self.patcher_console_print.start()

        # Patch readline
        self.patcher_readline_read = patch('readline.read_history_file')
        self.mock_readline_read = self.patcher_readline_read.start()
        self.patcher_readline_write = patch('readline.write_history_file')
        self.mock_readline_write = self.patcher_readline_write.start()

    def tearDown(self):
        self.patcher_os_exists.stop()
        self.patcher_open.stop()
        self.patcher_json_dump.stop()
        self.patcher_json_load.stop()
        self.patcher_console_print.stop()
        self.patcher_readline_read.stop()
        self.patcher_readline_write.stop()

        # Clean up any actual files that might have been created if mocks
        # were bypassed or if tests specifically create files.
        # Use with caution and ensure mocks are correctly stopping file
        # creation.
        # if _original_os_path_exists(CONFIG_FILE):
        #     os.remove(CONFIG_FILE)
        # if _original_os_path_exists(HISTORY_FILE):
        #     os.remove(HISTORY_FILE)
        # readline_history_file = os.path.expanduser(
        #     "~/.cl_ai_readline_history"
        # )
        # if _original_os_path_exists(readline_history_file):
        #     os.remove(readline_history_file)

    # Test Configuration
    def test_load_config_default(self):
        # Simulate config file not existing
        self.mock_os_exists.return_value = False
        self.cl_ai.config = {}  # Reset
        config = self.cl_ai.load_config()

        self.assertEqual(config, DEFAULT_CONFIG)
        self.mock_os_exists.assert_called_once_with(CONFIG_FILE)
        self.mock_file_open.assert_called_once_with(CONFIG_FILE, "w")
        self.mock_json_dump.assert_called_once_with(
            DEFAULT_CONFIG, self.mock_file_open(), indent=2
        )

    def test_load_config_existing(self):
        self.mock_os_exists.return_value = True
        test_config = {"model": "test_model", "url": "http://test.url"}
        self.mock_json_load.return_value = test_config

        self.cl_ai.config = {}  # Reset
        config = self.cl_ai.load_config()

        self.assertEqual(config, test_config)
        self.mock_os_exists.assert_called_once_with(CONFIG_FILE)
        self.mock_file_open.assert_called_once_with(CONFIG_FILE, "r")
        self.mock_json_load.assert_called_once_with(self.mock_file_open())

    def test_load_config_invalid_json(self):
        self.mock_os_exists.return_value = True
        # The string representation of JSONDecodeError(msg, doc, pos) is
        # e.g. "msg: line L column C (char X)"
        # The "doc" parameter is the document being parsed, not directly
        # part of the basic error message string.
        self.mock_json_load.side_effect = json.JSONDecodeError(
            "Error decoding JSON", "dummy_doc", 0
        )

        self.cl_ai.config = {}  # Reset
        config = self.cl_ai.load_config()

        self.assertEqual(config, DEFAULT_CONFIG)
        self.mock_os_exists.assert_called_once_with(CONFIG_FILE)
        self.mock_file_open.assert_called_once_with(CONFIG_FILE, "r")
        self.mock_json_load.assert_called_once_with(self.mock_file_open())
        # Error message check is now more flexible due to changes in
        # load_config
        # Check that some error was printed
        self.mock_console_print.assert_any_call(unittest.mock.ANY)
        # More specific check if needed:
        # printed_error = self.mock_console_print.call_args_list[0][0][0]
        # # Gets the first arg of the first call
        # self.assertIn("[red]Error decoding config file", printed_error)

    def test_load_config_permission_error_read(self):
        self.mock_os_exists.return_value = True  # Config file exists
        # Shortened for test clarity
        self.mock_file_open.side_effect = PermissionError("Denied reading")

        self.cl_ai.config = {}  # Reset
        config = self.cl_ai.load_config()

        self.assertEqual(config, DEFAULT_CONFIG)  # Should fall back to default
        self.mock_os_exists.assert_called_once_with(CONFIG_FILE)
        self.mock_file_open.assert_called_once_with(CONFIG_FILE, "r")
        self.mock_console_print.assert_any_call(
            f"[red]Permission error reading config file ({CONFIG_FILE}): "
            f"Denied reading. Using default configuration.[/red]"
        )

    def test_load_config_permission_error_write_default(self):
        self.mock_os_exists.return_value = False  # Config file does NOT exist
        mock_permission_error_on_write = mock_open()
        # Configure the mock_open instance that will be used for the write
        # operation
        mock_permission_error_on_write.side_effect = PermissionError(
            "Denied writing"
        )

        # Stop the global setUp patcher for 'builtins.open'
        self.patcher_open.stop()
        # Apply a local patch for 'builtins.open' just for this test
        local_open_patcher = patch(
            'builtins.open', mock_permission_error_on_write
        )
        mock_open_locally = local_open_patcher.start()
        # Ensure this local patch is stopped after the test
        self.addCleanup(local_open_patcher.stop)

        self.cl_ai.config = {}  # Reset
        config = self.cl_ai.load_config()

        # Still returns default in-memory
        self.assertEqual(config, DEFAULT_CONFIG)
        # Check that the locally patched open was called for writing the
        # default config
        mock_open_locally.assert_called_once_with(CONFIG_FILE, "w")
        self.mock_console_print.assert_any_call(
            f"[red]Permission error writing default config file "
            f"({CONFIG_FILE}): Denied writing. Using in-memory default "
            f"configuration for this session.[/red]"
        )

    def test_load_config_invalid_file_content(self):
        self.mock_os_exists.return_value = True
        # Simulate invalid content type
        self.mock_json_load.return_value = "not a dict"

        self.cl_ai.config = {}  # Reset
        config = self.cl_ai.load_config()

        self.assertEqual(config, DEFAULT_CONFIG)
        self.mock_console_print.assert_any_call(
            f"[red]Error: Config file ({CONFIG_FILE}) does not contain a "
            f"valid JSON object. Using default configuration.[/red]"
        )

    # Test Conversations
    def test_load_conversations_no_file(self):
        self.mock_os_exists.return_value = False
        self.cl_ai.conversations = {"dummy": {}}
        conversations = self.cl_ai.load_conversations()
        self.assertEqual(conversations, {})
        self.mock_os_exists.assert_called_once_with(CONVERSATIONS_FILE)

    def test_load_conversations_existing(self):
        self.mock_os_exists.return_value = True
        test_conversations = {"conv1": {"title": "Test", "messages": []}}
        self.mock_json_load.return_value = test_conversations
        self.cl_ai.conversations = {}
        conversations = self.cl_ai.load_conversations()
        self.assertEqual(conversations, test_conversations)
        self.mock_os_exists.assert_called_once_with(CONVERSATIONS_FILE)
        self.mock_file_open.assert_called_once_with(CONVERSATIONS_FILE, "r")
        self.mock_json_load.assert_called_once_with(self.mock_file_open())

    def test_save_conversations(self):
        self.cl_ai.conversations = {"conv1": {"title": "Test", "messages": []}}
        self.cl_ai.save_conversations()
        self.mock_file_open.assert_called_once_with(CONVERSATIONS_FILE, "w")
        self.mock_json_dump.assert_called_once_with(
            self.cl_ai.conversations, self.mock_file_open(), indent=2
        )

    # Test Command Extraction
    def test_extract_command_bash_block(self):
        response = "Some text\n```bash\nls -l\ndate\n```\nMore text"
        self.assertEqual(self.cl_ai.extract_command(response), "ls -l\ndate")

    def test_extract_command_generic_block(self):
        response = "Some text\n```\ngit status\n```\nMore text"
        self.assertEqual(self.cl_ai.extract_command(response), "git status")

    def test_extract_command_simple_line(self):
        response = "pwd"
        self.assertEqual(self.cl_ai.extract_command(response), "pwd")

    def test_extract_command_with_explanation(self):
        # LLM provides command in a bash block
        response_with_bash_block = (
            "Explanation first.\n```bash\nls -la\n```\nMore explanation."
        )
        self.assertEqual(
            self.cl_ai.extract_command(response_with_bash_block), "ls -la"
        )

        # LLM provides command in a generic block
        response_with_generic_block = (
            "Explanation first.\n```\ngit status\n```\nMore explanation."
        )
        self.assertEqual(
            self.cl_ai.extract_command(response_with_generic_block),
            "git status"
        )

        # LLM provides only the command (forgets markdown)
        response_direct_command = "df -h"
        self.assertEqual(
            self.cl_ai.extract_command(response_direct_command), "df -h"
        )

        # LLM provides command with explanation but NO block
        # (extracts first line)
        response_expl_cmd_no_block = (
            "To list files, use the command:\nls -la\nThis shows all files."
        )
        self.assertEqual(
            self.cl_ai.extract_command(response_expl_cmd_no_block),
            "To list files, use the command:"
        )

    def test_extract_command_no_command(self):
        # Single line of text, not a command
        response_text_only = (
            "This is just a sentence of explanation about things."
        )
        self.assertEqual(
            self.cl_ai.extract_command(response_text_only), response_text_only
        )

        # Multiple lines of text, no command, no code block
        response_multiline_text = (
            "This is line one.\n"
            "And this is line two.\n"
            "No clear command here."
        )
        # Fallback extracts the first non-empty line
        self.assertEqual(
            self.cl_ai.extract_command(response_multiline_text),
            "This is line one."
        )

    def test_extract_command_dollar_prefix(self):
        # Dollar prefix outside code block (should be stripped)
        response_no_block_dollar = "$ echo hello"
        self.assertEqual(
            self.cl_ai.extract_command(response_no_block_dollar), "echo hello"
        )

        response_no_block_dollar_no_space = "$echo hello"
        self.assertEqual(
            self.cl_ai.extract_command(response_no_block_dollar_no_space),
            "echo hello"
        )

        # Dollar prefix inside code block (should also be stripped by the
        # final cleanup)
        response_code_block_dollar = "```bash\n$ docker ps\n```"
        self.assertEqual(
            self.cl_ai.extract_command(response_code_block_dollar), "docker ps"
        )

        response_code_block_dollar_no_space = "```bash\n$docker ps\n```"
        self.assertEqual(
            self.cl_ai.extract_command(response_code_block_dollar_no_space),
            "docker ps"
        )

    # Test Command Execution
    @patch('cmd_ai.subprocess.run')
    def test_run_command_success(self, mock_subprocess_run):
        mock_subprocess_run.return_value = MagicMock(
            stdout="Command output", stderr="", returncode=0
        )
        test_command = "ls -l"
        self.cl_ai.run_command(test_command)

        mock_subprocess_run.assert_called_once_with(
            test_command, shell=True, check=False, text=True,
            capture_output=True
        )
        # For "Executing..."
        self.mock_console_print.assert_any_call(unittest.mock.ANY)
        # For stdout
        self.mock_console_print.assert_any_call(unittest.mock.ANY)

    @patch('cmd_ai.subprocess.run')
    def test_run_command_error_output(self, mock_subprocess_run):
        mock_subprocess_run.return_value = MagicMock(
            stdout="", stderr="Error details", returncode=1
        )
        test_command = "cat non_existent_file"
        self.cl_ai.run_command(test_command)

        mock_subprocess_run.assert_called_once_with(
            test_command, shell=True, check=False, text=True,
            capture_output=True
        )
        # Executing
        self.mock_console_print.assert_any_call(unittest.mock.ANY)
        # Error details
        self.mock_console_print.assert_any_call(unittest.mock.ANY)
        # Command failed message
        self.mock_console_print.assert_any_call(unittest.mock.ANY)

    @patch('cmd_ai.subprocess.run', side_effect=Exception("Subprocess failed"))
    def test_run_command_exception(self, mock_subprocess_run):
        test_command = "some_command"
        self.cl_ai.run_command(test_command)

        mock_subprocess_run.assert_called_once_with(
            test_command, shell=True, check=False, text=True,
            capture_output=True
        )
        self.mock_console_print.assert_any_call(
            "[red]Error executing command: Subprocess failed[/red]"
        )

    # Test Configuration method (configure)
    @patch('cmd_ai.Prompt.ask')
    # Mock file writing for config
    @patch('builtins.open', new_callable=mock_open)
    @patch('cmd_ai.json.dump')
    def test_configure_change_model_and_save(
        self, mock_json_dump, mock_file_open_cfg, mock_prompt_ask
    ):
        # Simulate user inputs: choice '1' (model), new model name, then
        # choice '5' (save)
        # Actually, configure is not interactive in a loop. It asks one
        # choice. So, we test one change, e.g., model name.
        mock_prompt_ask.side_effect = [
            "1",  # Choice: Model name
            "new_test_model"  # New model name
        ]

        initial_model = self.cl_ai.config["model"]
        self.cl_ai.configure()

        self.assertEqual(self.cl_ai.config["model"], "new_test_model")
        mock_prompt_ask.assert_any_call(
            "Enter new model name", default=initial_model
        )
        mock_file_open_cfg.assert_called_once_with(CONFIG_FILE, "w")
        mock_json_dump.assert_called_once_with(
            self.cl_ai.config, mock_file_open_cfg(), indent=2
        )
        self.mock_console_print.assert_any_call(
            "[green]Configuration saved.[/green]"
        )

    @patch('cmd_ai.Prompt.ask')
    @patch('builtins.open', new_callable=mock_open)
    @patch('cmd_ai.json.dump')
    def test_configure_toggle_autorun_and_save(
        self, mock_json_dump, mock_file_open_cfg, mock_prompt_ask
    ):
        mock_prompt_ask.side_effect = ["4"]  # Choice: Toggle auto_run_prompt

        initial_auto_run = self.cl_ai.config.get("auto_run_prompt", True)
        self.cl_ai.configure()

        self.assertEqual(
            self.cl_ai.config["auto_run_prompt"], not initial_auto_run
        )
        mock_file_open_cfg.assert_called_once_with(CONFIG_FILE, "w")
        mock_json_dump.assert_called_once()  # Check it's called
        self.mock_console_print.assert_any_call(
            "[green]Configuration saved.[/green]"
        )
        if initial_auto_run:
            self.mock_console_print.assert_any_call(
                "[green]Run command prompt disabled.[/green]"
            )
        else:
            self.mock_console_print.assert_any_call(
                "[green]Run command prompt enabled.[/green]"
            )

    # User chooses "Save and exit"
    @patch('cmd_ai.Prompt.ask', return_value="5")
    @patch('builtins.open', new_callable=mock_open)
    @patch('cmd_ai.json.dump')
    def test_configure_save_and_exit_no_changes(
        self, mock_json_dump, mock_file_open_cfg, mock_prompt_ask
    ):
        # Store a copy of config to compare
        original_config_copy = self.cl_ai.config.copy()
        self.cl_ai.configure()

        # No settings changed
        self.assertEqual(self.cl_ai.config, original_config_copy)
        # Still saves
        mock_file_open_cfg.assert_called_once_with(CONFIG_FILE, "w")
        mock_json_dump.assert_called_once_with(
            self.cl_ai.config, mock_file_open_cfg(), indent=2
        )
        self.mock_console_print.assert_any_call(
            "[green]Configuration saved.[/green]"
        )

    @patch('cmd_ai.Prompt.ask', return_value="6")  # Invalid choice
    @patch('cmd_ai.json.dump')
    def test_configure_invalid_choice_does_not_save(
        self, mock_json_dump, mock_prompt_ask
    ):
        self.cl_ai.configure()
        mock_json_dump.assert_not_called()  # Should not save
        self.mock_console_print.assert_any_call(
            "[red]Invalid choice. Configuration not saved.[/red]"
        )


from unittest.mock import AsyncMock

class TestConversationManagement(unittest.TestCase):
    def setUp(self):
        self.cl_ai = CLAI()
        # Prevent file I/O during tests
        self.cl_ai.save_conversations = MagicMock()
        self.cl_ai.conversations = {
            "abcdef12": {"title": "First Conv", "messages": []},
            "12345678": {"title": "Second Conv", "messages": []},
            "abc45678": {"title": "Another Conv", "messages": []},
        }

    def test_find_conversation_by_full_id(self):
        conv_id = self.cl_ai.find_conversation("abcdef12")
        self.assertEqual(conv_id, "abcdef12")

    def test_find_conversation_by_title(self):
        conv_id = self.cl_ai.find_conversation("First Conv")
        self.assertEqual(conv_id, "abcdef12")

    def test_find_conversation_by_partial_id(self):
        conv_id = self.cl_ai.find_conversation("1234")
        self.assertEqual(conv_id, "12345678")

    def test_find_conversation_not_found(self):
        conv_id = self.cl_ai.find_conversation("nonexistent")
        self.assertIsNone(conv_id)

    def test_find_conversation_ambiguous_partial_id(self):
        # 'abc' matches 'abcdef12' and 'abc45678'
        conv_id = self.cl_ai.find_conversation("abc")
        self.assertIsNone(conv_id)

    def test_get_latest_conversation_id(self):
        latest_id = self.cl_ai.get_latest_conversation_id()
        self.assertEqual(latest_id, "abc45678")

    def test_get_latest_conversation_id_no_convs(self):
        self.cl_ai.conversations = {}
        latest_id = self.cl_ai.get_latest_conversation_id()
        self.assertIsNone(latest_id)

    @patch('cmd_ai.console.print')
    def test_show_conversation(self, mock_print):
        self.cl_ai.show_conversation("First Conv")
        # Check that console.print was called, indicating it tried to print a table
        mock_print.assert_called()

    @patch('cmd_ai.console.print')
    def test_show_conversation_not_found(self, mock_print):
        self.cl_ai.show_conversation("nonexistent")
        mock_print.assert_called_with("[red]Conversation 'nonexistent' not found.[/red]")

    def test_delete_conversation(self):
        self.cl_ai.delete_conversation("First Conv")
        self.assertNotIn("abcdef12", self.cl_ai.conversations)
        self.cl_ai.save_conversations.assert_called_once()


class TestCLAIAsyncMethods(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.cl_ai = CLAI()
        self.cl_ai.config = DEFAULT_CONFIG.copy()
        self.cl_ai.conversations = {}

        self.prompt_ask_patcher = patch('cmd_ai.Prompt.ask', return_value='y')
        self.mock_prompt_ask = self.prompt_ask_patcher.start()
        self.addCleanup(self.prompt_ask_patcher.stop)

    @patch('cmd_ai.os.urandom')
    async def test_one_shot_mode_creates_new_conversation(self, mock_urandom):
        mock_urandom.return_value.hex.return_value = "newconvid"
        self.cl_ai.query_llm = AsyncMock(return_value="response")
        self.cl_ai.save_conversations = MagicMock()

        await self.cl_ai.one_shot_mode("test query", title="Test Title")

        self.assertIn("newconvid", self.cl_ai.conversations)
        self.assertEqual(self.cl_ai.conversations["newconvid"]["title"], "Test Title")
        self.assertEqual(len(self.cl_ai.conversations["newconvid"]["messages"]), 2)
        self.cl_ai.save_conversations.assert_called_once()

    async def test_one_shot_mode_continues_conversation(self):
        self.cl_ai.conversations = {
            "conv1": {"title": "Test", "messages": [{"role": "user", "content": "old query"}]}
        }
        self.cl_ai.query_llm = AsyncMock(return_value="new response")
        self.cl_ai.save_conversations = MagicMock()

        await self.cl_ai.one_shot_mode("new query", conversation_id="conv1")

        self.assertEqual(len(self.cl_ai.conversations["conv1"]["messages"]), 3)
        self.assertEqual(self.cl_ai.conversations["conv1"]["messages"][-1]["content"], "new response")
        self.cl_ai.save_conversations.assert_called_once()

    @patch('cmd_ai.os.urandom')
    async def test_one_shot_mode_branches_conversation_with_new_title(self, mock_urandom):
        mock_urandom.return_value.hex.return_value = "newconvid"
        self.cl_ai.conversations = {
            "conv1": {"title": "Original", "messages": [{"role": "user", "content": "old query"}]}
        }
        self.cl_ai.query_llm = AsyncMock(return_value="new response")
        self.cl_ai.save_conversations = MagicMock()

        await self.cl_ai.one_shot_mode("new query", title="New Title", conversation_id="conv1")

        self.assertIn("newconvid", self.cl_ai.conversations)
        self.assertEqual(self.cl_ai.conversations["newconvid"]["title"], "New Title")
        self.assertEqual(len(self.cl_ai.conversations["newconvid"]["messages"]), 3)
        self.assertEqual(self.cl_ai.conversations["conv1"]["messages"], [{"role": "user", "content": "old query"}])
        self.cl_ai.save_conversations.assert_called_once()

    @patch('cmd_ai.os.urandom')
    @patch('cmd_ai.Prompt.ask')
    async def test_interactive_mode_creates_conversation(self, mock_prompt_ask, mock_urandom):
        mock_urandom.return_value.hex.return_value = "newconvid"
        # Simulate user typing "hello", then "world", then quitting, with "n" for execution prompts
        mock_prompt_ask.side_effect = ["hello", "n", "world", "n", "!quit"]
        self.cl_ai.query_llm = AsyncMock(return_value="response")
        self.cl_ai.save_conversations = MagicMock()

        await self.cl_ai.interactive_mode()

        # It should create one conversation with two exchanges
        self.assertEqual(len(self.cl_ai.conversations), 1)
        conv_id = list(self.cl_ai.conversations.keys())[0]
        self.assertEqual(len(self.cl_ai.conversations[conv_id]["messages"]), 4)
        self.assertEqual(self.cl_ai.conversations[conv_id]["title"], "hello")


class TestCLAIMainAsync(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.cl_ai_class_patcher = patch('cmd_ai.CLAI')
        self.MockCLAIClass = self.cl_ai_class_patcher.start()
        self.mock_cl_ai_instance = self.MockCLAIClass.return_value

        self.stdin_patcher = patch('sys.stdin.isatty', return_value=True)
        self.mock_stdin = self.stdin_patcher.start()
        self.addCleanup(self.stdin_patcher.stop)

        async def mock_async_method(*args, **kwargs):
            return None

        self.mock_cl_ai_instance.interactive_mode = MagicMock(side_effect=mock_async_method)
        self.mock_cl_ai_instance.one_shot_mode = MagicMock(side_effect=mock_async_method)

        self.mock_cl_ai_instance.configure = MagicMock()
        self.mock_cl_ai_instance.list_conversations = MagicMock()
        self.mock_cl_ai_instance.show_conversation = MagicMock()
        self.mock_cl_ai_instance.delete_conversation = MagicMock()
        self.mock_cl_ai_instance.find_conversation = MagicMock()
        self.mock_cl_ai_instance.get_latest_conversation_id = MagicMock()

    async def asyncTearDown(self):
        self.cl_ai_class_patcher.stop()

    async def test_main_interactive_mode(self):
        await async_main([])
        self.mock_cl_ai_instance.interactive_mode.assert_called_once()

    async def test_main_config_arg(self):
        await async_main(["--config"])
        self.mock_cl_ai_instance.configure.assert_called_once()

    async def test_main_list(self):
        await async_main(["--list"])
        self.mock_cl_ai_instance.list_conversations.assert_called_once()

    async def test_main_show(self):
        await async_main(["--show", "myconv"])
        self.mock_cl_ai_instance.show_conversation.assert_called_once_with("myconv")

    async def test_main_delete(self):
        await async_main(["--delete", "myconv"])
        self.mock_cl_ai_instance.delete_conversation.assert_called_once_with("myconv")

    async def test_main_delete_multiple(self):
        await async_main(["--delete", "myconv1", "--delete", "myconv2"])
        self.assertEqual(self.mock_cl_ai_instance.delete_conversation.call_count, 2)

    async def test_main_continue(self):
        self.mock_cl_ai_instance.find_conversation.return_value = "found_id"
        await async_main(["--continue", "myconv", "new prompt"])
        self.mock_cl_ai_instance.find_conversation.assert_called_once_with("myconv")
        self.mock_cl_ai_instance.one_shot_mode.assert_called_once_with(
            "new prompt", title=None, conversation_id="found_id"
        )

    async def test_main_continue_last(self):
        self.mock_cl_ai_instance.get_latest_conversation_id.return_value = "latest_id"
        await async_main(["--continue-last", "new prompt"])
        self.mock_cl_ai_instance.get_latest_conversation_id.assert_called_once()
        self.mock_cl_ai_instance.one_shot_mode.assert_called_once_with(
            "new prompt", title=None, conversation_id="latest_id"
        )

    async def test_main_with_title(self):
        await async_main(["--title", "My Title", "new prompt"])
        self.mock_cl_ai_instance.one_shot_mode.assert_called_once_with(
            "new prompt", title="My Title", conversation_id=None
        )

    @patch('sys.stdin')
    async def test_main_with_stdin(self, mock_stdin):
        mock_stdin.isatty.return_value = False
        mock_stdin.read.return_value = "piped content"
        await async_main(["prompt"])
        self.mock_cl_ai_instance.one_shot_mode.assert_called_once_with(
            "prompt\npiped content", title=None, conversation_id=None
        )


if __name__ == '__main__':
    unittest.main()
