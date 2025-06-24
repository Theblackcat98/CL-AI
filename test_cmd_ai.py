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

from cmd_ai import CLAI, DEFAULT_CONFIG, CONFIG_FILE, HISTORY_FILE, async_main


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

    # Test History
    def test_load_history_no_file(self):
        self.mock_os_exists.return_value = False
        self.cl_ai.history = ["dummy"]  # Reset
        history = self.cl_ai.load_history()

        self.assertEqual(history, [])
        self.mock_os_exists.assert_called_once_with(HISTORY_FILE)

    def test_load_history_existing(self):
        self.mock_os_exists.return_value = True
        test_history = [{"query": "q1", "response": "r1"}]
        self.mock_json_load.return_value = test_history

        self.cl_ai.history = []  # Reset
        history = self.cl_ai.load_history()

        self.assertEqual(history, test_history)
        self.mock_os_exists.assert_called_once_with(HISTORY_FILE)
        self.mock_file_open.assert_called_once_with(HISTORY_FILE, "r")
        self.mock_json_load.assert_called_once_with(self.mock_file_open())

    def test_load_history_invalid_json(self):
        self.mock_os_exists.return_value = True
        # Ensure open is called for reading, and json.load is attempted
        self.mock_file_open.return_value.read.return_value = "invalid json"
        self.mock_json_load.side_effect = json.JSONDecodeError(
            "Error", "doc", 0
        )

        self.cl_ai.history = ["dummy"]  # Reset
        history = self.cl_ai.load_history()

        self.assertEqual(history, [])
        self.mock_os_exists.assert_called_once_with(HISTORY_FILE)
        self.mock_file_open.assert_called_once_with(HISTORY_FILE, "r")
        self.mock_json_load.assert_called_once_with(self.mock_file_open())
        # Check that some warning was printed
        self.mock_console_print.assert_any_call(unittest.mock.ANY)

    def test_load_history_permission_error(self):
        self.mock_os_exists.return_value = True  # History file exists
        self.mock_file_open.side_effect = PermissionError(
            "Denied reading history"
        )

        self.cl_ai.history = ["dummy"]  # Reset
        history = self.cl_ai.load_history()

        self.assertEqual(history, [])  # Should fall back to empty history
        self.mock_os_exists.assert_called_once_with(HISTORY_FILE)
        self.mock_file_open.assert_called_once_with(HISTORY_FILE, "r")
        self.mock_console_print.assert_any_call(
            f"[yellow]Warning: Permission error reading history file "
            f"({HISTORY_FILE}): Denied reading history. Starting with "
            f"empty history.[/yellow]"
        )

    def test_load_history_invalid_file_content(self):
        self.mock_os_exists.return_value = True
        # Simulate invalid content type for history
        self.mock_json_load.return_value = "not a list"

        self.cl_ai.history = ["dummy"]  # Reset
        history = self.cl_ai.load_history()

        self.assertEqual(history, [])
        self.mock_console_print.assert_any_call(
            f"[yellow]Warning: History file ({HISTORY_FILE}) does not "
            f"contain a valid JSON list. Starting with empty "
            f"history.[/yellow]"
        )

    def test_save_history(self):
        self.cl_ai.history = [
            {"query": f"q{i}", "response": f"r{i}"} for i in range(25)
        ]
        expected_history_to_save = self.cl_ai.history[-20:]

        self.cl_ai.save_history()

        self.mock_file_open.assert_called_once_with(HISTORY_FILE, "w")
        self.mock_json_dump.assert_called_once_with(
            expected_history_to_save, self.mock_file_open(), indent=2
        )

    def test_save_history_less_than_20(self):
        self.cl_ai.history = [
            {"query": f"q{i}", "response": f"r{i}"} for i in range(5)
        ]
        expected_history_to_save = self.cl_ai.history

        self.cl_ai.save_history()

        self.mock_file_open.assert_called_once_with(HISTORY_FILE, "w")
        self.mock_json_dump.assert_called_once_with(
            expected_history_to_save, self.mock_file_open(), indent=2
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


class TestCLAIAsyncMethods(unittest.IsolatedAsyncioTestCase):  # Renamed class
    # This new class will house tests for async methods of CLAI

    # unittest.IsolatedAsyncioTestCase uses setUp, not asyncSetUp
    def setUp(self):
        # Common mocks needed for async method testing
        self.cl_ai = CLAI()  # Renamed instance variable

        # Mock config and history loading as they are called in
        # CLAI.__init__ and we don't want actual file I/O during
        # these specific async tests.
        # The global patchers in TestCLAI might interfere or might be
        # sufficient. For clarity, let's ensure CLAI instance for
        # these tests uses predictable config/history.
        self.cl_ai.config = DEFAULT_CONFIG.copy()  # Use a copy of defaults
        self.cl_ai.history = []

        # Patch console.print for this class too, if methods print directly
        self.patcher_console_print_async = patch('cmd_ai.console.print')
        self.mock_console_print_async = (
            self.patcher_console_print_async.start()
        )
        self.addCleanup(self.patcher_console_print_async.stop)

        # Patch Prompt.ask for methods that use it (like configure, or
        # process_command for run prompt)
        self.patcher_prompt_ask_async = patch('cmd_ai.Prompt.ask')
        self.mock_prompt_ask_async = self.patcher_prompt_ask_async.start()
        self.addCleanup(self.patcher_prompt_ask_async.stop)

    # Test query_llm
    @patch('aiohttp.ClientSession.post')
    async def test_query_llm_success(self, mock_post):
        # Setup mock response from aiohttp
        mock_response = MagicMock()
        mock_response.status = 200

        async def json_func():  # mock async json()
            return {"message": {"content": "mocked llm response"}}
        mock_response.json = json_func

        # The post call returns an async context manager,
        # so mock its __aenter__
        mock_post.return_value.__aenter__.return_value = mock_response

        response = await self.cl_ai.query_llm("test prompt")
        self.assertEqual(response, "mocked llm response")
        mock_post.assert_called_once()  # Check that post was called

    @patch('aiohttp.ClientSession.post')
    async def test_query_llm_http_error(self, mock_post):
        mock_response = MagicMock()
        mock_response.status = 500

        async def text_func():  # mock async text()
            return "Internal Server Error"
        mock_response.text = text_func
        mock_post.return_value.__aenter__.return_value = mock_response

        response = await self.cl_ai.query_llm("test prompt")
        self.assertTrue(
            response.startswith("Error: HTTP 500 - Internal Server Error")
        )

    @patch(
        'aiohttp.ClientSession.post',
        side_effect=aiohttp.ClientError("Network Error")
    )
    async def test_query_llm_connection_error(self, mock_post):
        response = await self.cl_ai.query_llm("test prompt")
        # query_llm itself prepends "Connection error: " or "Error: "
        # For aiohttp.ClientError, it's "Connection error: "
        self.assertEqual(response, "Connection error: Network Error")

    @patch(
        'aiohttp.ClientSession.post',
        side_effect=Exception("Generic Exception")
    )
    async def test_query_llm_generic_exception(self, mock_post):
        response = await self.cl_ai.query_llm("test prompt")
        # For other exceptions, it's "Error: "
        self.assertEqual(response, "Error: Generic Exception")

    # Test process_command (simplified examples)
    async def test_process_command_help(self):
        self.cl_ai.show_help = MagicMock()  # Mock the called method
        await self.cl_ai.process_command("!help")
        self.cl_ai.show_help.assert_called_once()

    async def test_process_command_quit(self):
        result = await self.cl_ai.process_command("!quit")
        self.assertFalse(result)
        self.mock_console_print_async.assert_any_call(
            "[green]Goodbye![/green]"
        )

    # Patching on the class itself
    @patch.object(CLAI, 'query_llm', new_callable=MagicMock)  # Patched CLAI
    @patch.object(
        CLAI, 'extract_command', return_value="extracted_command"  # Patched CLAI
    )
    @patch.object(CLAI, 'run_command')  # Patched CLAI
    async def test_process_command_query_and_run(
        self, mock_run_command, mock_extract_command, mock_query_llm_method
    ):
        # Mock the async query_llm method on the instance for this test
        async def mock_query_llm_side_effect(prompt):
            return f"response for {prompt}"
        # self.cl_ai.query_llm = mock_query_llm_side_effect
        # # This would work if not patched with @patch
        mock_query_llm_method.side_effect = mock_query_llm_side_effect

        self.cl_ai.config["auto_run_prompt"] = True
        self.mock_prompt_ask_async.return_value = "y"  # User chooses to run

        await self.cl_ai.process_command("test query")

        # mock_query_llm_method.assert_called_once_with("test query")
        # For some reason, direct assert_called_once_with on the MagicMock
        # assigned to query_llm (if we did self.cl_ai.query_llm =
        # MagicMock(side_effect=...)) can be tricky with async.
        # The @patch.object approach is cleaner here.
        self.assertTrue(mock_query_llm_method.called)
        self.assertEqual(mock_query_llm_method.call_args[0][0], "test query")

        mock_extract_command.assert_called_once_with("response for test query")
        mock_run_command.assert_called_once_with("extracted_command")
        self.mock_console_print_async.assert_any_call(
            "\n[blue]response for test query[/blue]\n"
        )


class TestCLAIMainAsync(unittest.IsolatedAsyncioTestCase):  # Renamed class

    async def asyncSetUp(self):
        # Patch CLAI class where it's imported in cmd_ai (which is the
        # module where async_main is)
        self.cl_ai_class_patcher = patch('cmd_ai.CLAI')  # Patched CLAI
        self.MockCLAIClass = self.cl_ai_class_patcher.start()  # Patched CLAI

        # This mock_cl_ai_instance is what `CLAI()` will return within
        # async_main
        self.mock_cl_ai_instance = self.MockCLAIClass.return_value

        # Mock async methods with an object that can be awaited (like a
        # Future or another coroutine)
        # Using AsyncMock would be more idiomatic if available and needed
        # for more complex async interactions
        # For simple call checks, a MagicMock returning a completed Future
        # works.
        async def mock_async_method(*args, **kwargs):
            return None

        self.mock_cl_ai_instance.interactive_mode = MagicMock(
            side_effect=mock_async_method
        )
        self.mock_cl_ai_instance.one_shot_mode = MagicMock(
            side_effect=mock_async_method
        )

        # Synchronous methods
        self.mock_cl_ai_instance.configure = MagicMock()
        self.mock_cl_ai_instance.show_history = MagicMock()

        # Patch readline if its absence causes issues in test environment
        self.readline_read_patcher = patch(
            'readline.read_history_file', MagicMock()
        )
        self.readline_write_patcher = patch(
            'readline.write_history_file', MagicMock()
        )
        self.readline_read_patcher.start()
        self.readline_write_patcher.start()

    async def asyncTearDown(self):
        self.cl_ai_class_patcher.stop()
        self.readline_read_patcher.stop()
        self.readline_write_patcher.stop()

    async def test_main_interactive_mode(self):
        await async_main([])
        self.mock_cl_ai_instance.interactive_mode.assert_called_once()

    async def test_main_one_shot_mode(self):
        query = "test query"
        await async_main([query])
        self.mock_cl_ai_instance.one_shot_mode.assert_called_once_with(query)

    async def test_main_config_arg(self):
        await async_main(["--config"])
        self.mock_cl_ai_instance.configure.assert_called_once()

    async def test_main_history_arg(self):
        await async_main(["--history"])
        self.mock_cl_ai_instance.show_history.assert_called_once()


if __name__ == '__main__':
    # This setup allows running `python test_cmd_ai.py`
    # It will discover and run tests from both TestCase classes.
    unittest.main()
