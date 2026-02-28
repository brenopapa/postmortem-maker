"""
Testes para o cliente do Slack.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from src.slack_client import SlackClient
from src.config import SlackConfig


class TestSlackClient:
    """Testes para SlackClient."""

    @pytest.fixture
    def config(self):
        """Fixture para configuração."""
        return SlackConfig(
            bot_token="xoxb-test-token",
            user_token="xoxp-test-user-token"
        )

    @pytest.fixture
    def client(self, config):
        """Fixture para o cliente."""
        return SlackClient(config)

    def test_parse_thread_url_archives(self, client):
        """Testa parsing de URL com /archives/."""
        url = "https://workspace.slack.com/archives/C01234567/p1234567890123456"
        result = client.parse_thread_url(url)
        
        assert result is not None
        channel_id, thread_ts = result
        assert channel_id == "C01234567"
        assert thread_ts == "1234567890.123456"

    def test_parse_thread_url_invalid(self, client):
        """Testa URL inválida."""
        url = "https://google.com"
        result = client.parse_thread_url(url)
        
        assert result is None

    def test_parse_slack_timestamp(self, client):
        """Testa parsing de timestamp do Slack."""
        ts = "1234567890.123456"
        result = client._parse_slack_timestamp(ts)
        
        assert isinstance(result, datetime)
        assert result.year == 2009  # Unix timestamp referência

    def test_clean_message_text_simple(self, client):
        """Testa limpeza de texto simples."""
        text = "Hello World"
        result = client._clean_message_text(text)
        
        assert result == "Hello World"

    def test_clean_message_text_channel_mention(self, client):
        """Testa limpeza de menção de canal."""
        text = "Check <#C12345|general> channel"
        result = client._clean_message_text(text)
        
        assert "#general" in result

    def test_clean_message_text_url(self, client):
        """Testa limpeza de URL."""
        text = "See <https://example.com|example> for more"
        result = client._clean_message_text(text)
        
        assert "example" in result
        assert "https://example.com" in result

    def test_clean_message_text_empty(self, client):
        """Testa texto vazio."""
        result = client._clean_message_text("")
        
        assert result == ""

    @patch('requests.get')
    def test_get_user_name(self, mock_get, client):
        """Testa busca de nome de usuário."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "ok": True,
            "user": {"real_name": "João Silva", "name": "jsilva"}
        }
        mock_get.return_value = mock_response
        
        result = client.get_user_name("U12345")
        
        assert result == "João Silva"

    @patch('requests.get')
    def test_get_user_name_cached(self, mock_get, client):
        """Testa cache de nome de usuário."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "ok": True,
            "user": {"real_name": "João Silva"}
        }
        mock_get.return_value = mock_response
        
        # Primeira chamada
        client.get_user_name("U12345")
        # Segunda chamada deve usar cache
        result = client.get_user_name("U12345")
        
        assert result == "João Silva"
        assert mock_get.call_count == 1  # Apenas uma chamada

    @patch('requests.get')
    def test_get_channel_name(self, mock_get, client):
        """Testa busca de nome de canal."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "ok": True,
            "channel": {"name": "incidents"}
        }
        mock_get.return_value = mock_response
        
        result = client.get_channel_name("C12345")
        
        assert result == "incidents"

    @patch('requests.get')
    def test_test_connection_success(self, mock_get, client):
        """Testa conexão bem sucedida."""
        mock_response = Mock()
        mock_response.json.return_value = {"ok": True}
        mock_get.return_value = mock_response
        
        result = client.test_connection()
        
        assert result is True

    @patch('requests.get')
    def test_test_connection_failure(self, mock_get, client):
        """Testa falha de conexão."""
        mock_get.side_effect = Exception("Connection failed")
        
        result = client.test_connection()
        
        assert result is False

    @patch('requests.get')
    def test_get_thread_messages(self, mock_get, client):
        """Testa busca de mensagens de thread."""
        # Mock para conversations.info
        channel_response = Mock()
        channel_response.json.return_value = {
            "ok": True,
            "channel": {"name": "incidents"}
        }
        
        # Mock para conversations.replies
        replies_response = Mock()
        replies_response.json.return_value = {
            "ok": True,
            "messages": [
                {
                    "ts": "1234567890.000001",
                    "user": "U1",
                    "text": "First message"
                },
                {
                    "ts": "1234567890.000002",
                    "user": "U2",
                    "text": "Reply message"
                }
            ]
        }
        
        # Mock para users.info e chat.getPermalink
        user_response = Mock()
        user_response.json.return_value = {
            "ok": True,
            "user": {"real_name": "Test User"}
        }
        
        permalink_response = Mock()
        permalink_response.json.return_value = {
            "ok": True,
            "permalink": "https://slack.com/permalink"
        }
        
        def side_effect(*args, **kwargs):
            url = args[0]
            if "conversations.info" in url:
                return channel_response
            elif "conversations.replies" in url:
                return replies_response
            elif "users.info" in url:
                return user_response
            elif "chat.getPermalink" in url:
                return permalink_response
            return Mock(json=lambda: {"ok": True})
        
        mock_get.side_effect = side_effect
        
        messages = client.get_thread_messages("C12345", "1234567890.000001")
        
        assert len(messages) == 2
