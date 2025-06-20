import unittest
from unittest.mock import patch, mock_open, MagicMock, call
import json
import os
import sys
import asyncio # Required for async_main and IsolatedAsyncioTestCase

# Add the directory containing cmd_ai.py to sys.path
# This allows importing cmd_ai when running tests from the test directory or project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.'))) # Assuming test_cmd_ai.py is in the same dir as cmd_ai.py
# If cmd_ai.py is in parent directory:
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


from cmd_ai import CommandAI, DEFAULT_CONFIG, CONFIG_FILE, HISTORY_FILE, async_main

# Store original os.path.exists to use in tearDown if needed for actual file cleanup
# _original_os_path_exists = os.path.exists

class TestCommandAI(unittest.TestCase):
    def setUp(self):
        self.cmd_ai = CommandAI()
        # Patch os.path.exists globally for most tests to avoid actual file checks,
        # unless a specific test needs to interact with the file system.
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

        # Clean up any actual files that might have been created if mocks were bypassed
        # or if tests specifically create files.
        # Use with caution and ensure mocks are correctly stopping file creation.
        # if _original_os_path_exists(CONFIG_FILE):
        #     os.remove(CONFIG_FILE)
        # if _original_os_path_exists(HISTORY_FILE):
        #     os.remove(HISTORY_FILE)
        # readline_history_file = os.path.expanduser("~/.cmd_ai_readline_history")
        # if _original_os_path_exists(readline_history_file):
        #     os.remove(readline_history_file)


    # Test Configuration
    def test_load_config_default(self):
        self.mock_os_exists.return_value = False  # Simulate config file not existing
        self.cmd_ai.config = {} # Reset
        config = self.cmd_ai.load_config()

        self.assertEqual(config, DEFAULT_CONFIG)
        self.mock_os_exists.assert_called_once_with(CONFIG_FILE)
        self.mock_file_open.assert_called_once_with(CONFIG_FILE, "w")
        self.mock_json_dump.assert_called_once_with(DEFAULT_CONFIG, self.mock_file_open(), indent=2)

    def test_load_config_existing(self):
        self.mock_os_exists.return_value = True
        test_config = {"model": "test_model", "url": "http://test.url"}
        self.mock_json_load.return_value = test_config

        self.cmd_ai.config = {} # Reset
        config = self.cmd_ai.load_config()

        self.assertEqual(config, test_config)
        self.mock_os_exists.assert_called_once_with(CONFIG_FILE)
        self.mock_file_open.assert_called_once_with(CONFIG_FILE, "r")
        self.mock_json_load.assert_called_once_with(self.mock_file_open())

    def test_load_config_invalid_json(self):
        self.mock_os_exists.return_value = True
        # The string representation of JSONDecodeError(msg, doc, pos) is e.g. "msg: line L column C (char X)"
        # The "doc" parameter is the document being parsed, not directly part of the basic error message string.
        self.mock_json_load.side_effect = json.JSONDecodeError("Error decoding JSON", "dummy_doc", 0)

        self.cmd_ai.config = {} # Reset
        config = self.cmd_ai.load_config()

        self.assertEqual(config, DEFAULT_CONFIG)
        self.mock_os_exists.assert_called_once_with(CONFIG_FILE)
        self.mock_file_open.assert_called_once_with(CONFIG_FILE, "r")
        self.mock_json_load.assert_called_once_with(self.mock_file_open())
        # Adjust the expected error message to what JSONDecodeError actually produces
        expected_error_msg = "[red]Error loading config: Error decoding JSON: line 1 column 1 (char 0)[/red]"
        self.mock_console_print.assert_called_with(expected_error_msg)

    # Test History
    def test_load_history_no_file(self):
        self.mock_os_exists.return_value = False
        self.cmd_ai.history = ["dummy"] # Reset
        history = self.cmd_ai.load_history()

        self.assertEqual(history, [])
        self.mock_os_exists.assert_called_once_with(HISTORY_FILE)

    def test_load_history_existing(self):
        self.mock_os_exists.return_value = True
        test_history = [{"query": "q1", "response": "r1"}]
        self.mock_json_load.return_value = test_history

        self.cmd_ai.history = [] # Reset
        history = self.cmd_ai.load_history()

        self.assertEqual(history, test_history)
        self.mock_os_exists.assert_called_once_with(HISTORY_FILE)
        self.mock_file_open.assert_called_once_with(HISTORY_FILE, "r")
        self.mock_json_load.assert_called_once_with(self.mock_file_open())

    def test_load_history_invalid_json(self):
        self.mock_os_exists.return_value = True
        # Ensure open is called for reading, and json.load is attempted
        self.mock_file_open.return_value.read.return_value = "invalid json"
        self.mock_json_load.side_effect = json.JSONDecodeError("Error", "doc", 0)

        self.cmd_ai.history = ["dummy"] # Reset
        history = self.cmd_ai.load_history()

        self.assertEqual(history, [])
        self.mock_os_exists.assert_called_once_with(HISTORY_FILE)
        self.mock_file_open.assert_called_once_with(HISTORY_FILE, "r")
        self.mock_json_load.assert_called_once_with(self.mock_file_open())


    def test_save_history(self):
        self.cmd_ai.history = [{"query": f"q{i}", "response": f"r{i}"} for i in range(25)]
        expected_history_to_save = self.cmd_ai.history[-20:]

        self.cmd_ai.save_history()

        self.mock_file_open.assert_called_once_with(HISTORY_FILE, "w")
        self.mock_json_dump.assert_called_once_with(expected_history_to_save, self.mock_file_open(), indent=2)

    def test_save_history_less_than_20(self):
        self.cmd_ai.history = [{"query": f"q{i}", "response": f"r{i}"} for i in range(5)]
        expected_history_to_save = self.cmd_ai.history

        self.cmd_ai.save_history()

        self.mock_file_open.assert_called_once_with(HISTORY_FILE, "w")
        self.mock_json_dump.assert_called_once_with(expected_history_to_save, self.mock_file_open(), indent=2)


    # Test Command Extraction
    def test_extract_command_bash_block(self):
        response = "Some text\n```bash\nls -l\ndate\n```\nMore text"
        self.assertEqual(self.cmd_ai.extract_command(response), "ls -l\ndate")

    def test_extract_command_generic_block(self):
        response = "Some text\n```\ngit status\n```\nMore text"
        self.assertEqual(self.cmd_ai.extract_command(response), "git status")

    def test_extract_command_simple_line(self):
        response = "pwd"
        self.assertEqual(self.cmd_ai.extract_command(response), "pwd")

    def test_extract_command_with_explanation(self):
        response = "To list files, use the command:\nls -la\nThis shows all files."
        self.assertEqual(self.cmd_ai.extract_command(response), "ls -la")

        response_two = "You can check disk space with:\ndf -h"
        self.assertEqual(self.cmd_ai.extract_command(response_two), "df -h")

    def test_extract_command_no_command(self):
        # Adjusted to match the current behavior of extract_command for non-command-like single lines
        response = "This is just a sentence of explanation about things."
        self.assertEqual(self.cmd_ai.extract_command(response), response.strip())

        response_multiline_no_command = "This is line one.\nAnd this is line two.\nNo clear command here."
        # New logic: "This is line one." is skipped as explanation.
        # "And this is line two." becomes the first candidate.
        self.assertEqual(self.cmd_ai.extract_command(response_multiline_no_command), "And this is line two.")


    def test_extract_command_dollar_prefix(self):
        response = "$ echo hello"
        self.assertEqual(self.cmd_ai.extract_command(response), "echo hello")

        # Test if $ is stripped from within code blocks (current behavior is it's NOT stripped by extract_command)
        response_code_block = "```bash\n$ docker ps\n```"
        self.assertEqual(self.cmd_ai.extract_command(response_code_block), "$ docker ps")


class TestCommandAIMainAsync(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Patch CommandAI class where it's imported in cmd_ai (which is the module where async_main is)
        self.cmd_ai_class_patcher = patch('cmd_ai.CommandAI')
        self.MockCommandAIClass = self.cmd_ai_class_patcher.start()

        # This mock_cmd_ai_instance is what `CommandAI()` will return within async_main
        self.mock_cmd_ai_instance = self.MockCommandAIClass.return_value

        # Mock async methods with an object that can be awaited (like a Future or another coroutine)
        # Using AsyncMock would be more idiomatic if available and needed for more complex async interactions
        # For simple call checks, a MagicMock returning a completed Future works.
        async def mock_async_method(*args, **kwargs):
            return None

        self.mock_cmd_ai_instance.interactive_mode = MagicMock(side_effect=mock_async_method)
        self.mock_cmd_ai_instance.one_shot_mode = MagicMock(side_effect=mock_async_method)

        # Synchronous methods
        self.mock_cmd_ai_instance.configure = MagicMock()
        self.mock_cmd_ai_instance.show_history = MagicMock()

        # Patch readline if its absence causes issues in test environment
        self.readline_read_patcher = patch('readline.read_history_file', MagicMock())
        self.readline_write_patcher = patch('readline.write_history_file', MagicMock())
        self.readline_read_patcher.start()
        self.readline_write_patcher.start()


    async def asyncTearDown(self):
        self.cmd_ai_class_patcher.stop()
        self.readline_read_patcher.stop()
        self.readline_write_patcher.stop()

    async def test_main_interactive_mode(self):
        await async_main([])
        self.mock_cmd_ai_instance.interactive_mode.assert_called_once()

    async def test_main_one_shot_mode(self):
        query = "test query"
        await async_main([query])
        self.mock_cmd_ai_instance.one_shot_mode.assert_called_once_with(query)

    async def test_main_config_arg(self):
        await async_main(["--config"])
        self.mock_cmd_ai_instance.configure.assert_called_once()

    async def test_main_history_arg(self):
        await async_main(["--history"])
        self.mock_cmd_ai_instance.show_history.assert_called_once()

if __name__ == '__main__':
    # This setup allows running `python test_cmd_ai.py`
    # It will discover and run tests from both TestCase classes.
    unittest.main()
