import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import sys
import asyncio
import os

# Add the project root to sys.path so we can import cl_ai
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from cl_ai.core import CLAI
from cl_ai.llm import extract_command, query_llm


class TestCLAI(unittest.TestCase):

    def setUp(self):
        # Mock configuration and conversations files to avoid file I/O
        self.mock_config_patcher = patch('cl_ai.config.CONFIG_FILE', 'mock_config.json')
        self.mock_conversations_patcher = patch('cl_ai.config.CONVERSATIONS_FILE', 'mock_conversations.json')
        self.mock_config_patcher.start()
        self.mock_conversations_patcher.start()

        # Suppress console output during tests
        self.console_patcher = patch('cl_ai.ui.console.print')
        self.mock_console_print = self.console_patcher.start()

    def tearDown(self):
        self.mock_config_patcher.stop()
        self.mock_conversations_patcher.stop()
        self.console_patcher.stop()

    def test_extract_command_bash_block(self):
        """Test extracting command from a bash code block."""
        response = "Here is the command:\n```bash\nls -la\n```"
        self.assertEqual(extract_command(response), "ls -la")

    def test_extract_command_generic_block(self):
        """Test extracting command from a generic code block."""
        response = "Use this:\n```\ngit status\n```"
        self.assertEqual(extract_command(response), "git status")

    def test_extract_command_single_line(self):
        """Test extracting command from a single line response."""
        response = "mkdir new_dir"
        self.assertEqual(extract_command(response), "mkdir new_dir")

    def test_extract_command_with_dollar(self):
        """Test extracting command with leading $."""
        response = "```bash\n$ sudo apt update\n```"
        self.assertEqual(extract_command(response), "sudo apt update")

    def test_extract_command_multiline_fallback(self):
        """Test fallback for multiline response without code blocks."""
        response = "First line\nSecond line"
        # It should warn and take the first line
        self.assertEqual(extract_command(response), "First line")

    @patch('cl_ai.core.load_config')
    @patch('cl_ai.core.load_conversations')
    def test_initialization(self, mock_load_conversations, mock_load_config):
        """Test CLAI initialization."""
        mock_load_config.return_value = {"model": "test", "url": "http://test", "type": "ollama"}
        mock_load_conversations.return_value = {}

        cl_ai = CLAI()
        self.assertEqual(cl_ai.config["model"], "test")
        self.assertEqual(cl_ai.conversations, {})

    @patch('cl_ai.llm.aiohttp.ClientSession')
    def test_query_llm_success(self, mock_session):
        """Test successful LLM query."""
        # Setup async mock for session context manager
        mock_session_instance = MagicMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {"message": {"content": "Response"}}

        mock_session_instance.post.return_value.__aenter__.return_value = mock_response

        config = {"model": "test", "url": "http://test", "type": "ollama", "prompt_prefix": "prefix"}

        response = asyncio.run(query_llm(config, "test query"))
        self.assertEqual(response, "Response")

    @patch("cl_ai.core.list_conversations")
    def test_history_command_lists_conversations(self, mock_list_conversations):
        cl_ai = CLAI.__new__(CLAI)
        cl_ai.config = {}
        cl_ai.conversations = {"abcd": {"title": "Example", "messages": []}}

        keep_running, conversation_id = asyncio.run(
            cl_ai.process_command("!history")
        )

        self.assertTrue(keep_running)
        self.assertIsNone(conversation_id)
        mock_list_conversations.assert_called_once()
        self.assertIs(mock_list_conversations.call_args.args[0], cl_ai.conversations)

    @patch("cl_ai.core.save_conversations")
    def test_clear_command_removes_and_saves_history(self, mock_save_conversations):
        cl_ai = CLAI.__new__(CLAI)
        cl_ai.config = {}
        cl_ai.conversations = {"abcd": {"title": "Example", "messages": []}}

        keep_running, conversation_id = asyncio.run(
            cl_ai.process_command("!clear")
        )

        self.assertTrue(keep_running)
        self.assertIsNone(conversation_id)
        self.assertEqual(cl_ai.conversations, {})
        mock_save_conversations.assert_called_once()
        self.assertIs(mock_save_conversations.call_args.args[0], cl_ai.conversations)

if __name__ == '__main__':
    unittest.main()
