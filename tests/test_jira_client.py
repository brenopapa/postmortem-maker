"""
Testes para o cliente do Jira.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from src.jira_client import JiraClient
from src.config import JiraConfig


class TestJiraClient:
    """Testes para JiraClient."""

    @pytest.fixture
    def config(self):
        """Fixture para configuração."""
        return JiraConfig(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token"
        )

    @pytest.fixture
    def client(self, config):
        """Fixture para o cliente."""
        return JiraClient(config)

    def test_extract_issue_key_from_browse_url(self, client):
        """Testa extração de chave de URL /browse/."""
        url = "https://company.atlassian.net/browse/PROJ-123"
        result = client.extract_issue_key_from_url(url)
        
        assert result == "PROJ-123"

    def test_extract_issue_key_from_issues_url(self, client):
        """Testa extração de chave de URL /issues/."""
        url = "https://company.atlassian.net/issues/CAPL-9011"
        result = client.extract_issue_key_from_url(url)
        
        assert result == "CAPL-9011"

    def test_extract_issue_key_from_query_string(self, client):
        """Testa extração de chave de query string."""
        url = "https://company.atlassian.net/board?selectedIssue=REFI-1234"
        result = client.extract_issue_key_from_url(url)
        
        assert result == "REFI-1234"

    def test_extract_issue_key_invalid_url(self, client):
        """Testa URL inválida."""
        url = "https://google.com"
        result = client.extract_issue_key_from_url(url)
        
        assert result is None

    def test_parse_datetime(self, client):
        """Testa parsing de datetime do Jira."""
        date_str = "2026-02-18T21:25:00.000+0000"
        result = client._parse_datetime(date_str)
        
        assert result.year == 2026
        assert result.month == 2
        assert result.day == 18
        assert result.hour == 21
        assert result.minute == 25

    def test_parse_datetime_none(self, client):
        """Testa parsing com None."""
        result = client._parse_datetime(None)
        
        assert result is None

    def test_extract_text_from_adf_simple(self, client):
        """Testa extração de texto de ADF simples."""
        adf = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "Hello World"}
                    ]
                }
            ]
        }
        
        result = client._extract_text_from_adf(adf)
        
        assert "Hello World" in result

    def test_extract_text_from_adf_empty(self, client):
        """Testa extração de ADF vazio."""
        result = client._extract_text_from_adf(None)
        
        assert result == ""

    def test_get_user_display_name(self, client):
        """Testa extração de nome de usuário."""
        user_data = {"displayName": "João Silva", "name": "jsilva"}
        result = client._get_user_display_name(user_data)
        
        assert result == "João Silva"

    def test_get_user_display_name_fallback(self, client):
        """Testa fallback para name."""
        user_data = {"name": "jsilva"}
        result = client._get_user_display_name(user_data)
        
        assert result == "jsilva"

    def test_get_user_display_name_none(self, client):
        """Testa usuário None."""
        result = client._get_user_display_name(None)
        
        assert result == "Desconhecido"

    @patch('requests.get')
    def test_get_issue(self, mock_get, client):
        """Testa busca de issue."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "issues": [{
                "key": "PROJ-123",
                "fields": {
                    "summary": "Bug crítico",
                    "description": {"type": "doc", "content": []},
                    "status": {"name": "Done"},
                    "created": "2026-02-18T10:00:00.000+0000",
                    "updated": "2026-02-19T14:00:00.000+0000",
                    "resolutiondate": "2026-02-19T13:00:00.000+0000",
                    "assignee": {"displayName": "Maria Santos"},
                    "reporter": {"displayName": "João Silva"},
                    "comment": {"comments": []}
                }
            }]
        }
        mock_get.return_value = mock_response
        
        issue = client.get_issue("PROJ-123")
        
        assert issue.key == "PROJ-123"
        assert issue.summary == "Bug crítico"
        assert issue.assignee == "Maria Santos"
        assert issue.reporter == "João Silva"

    @patch('requests.get')
    def test_test_connection_success(self, mock_get, client):
        """Testa conexão bem sucedida."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"accountId": "123"}
        mock_get.return_value = mock_response
        
        result = client.test_connection()
        
        assert result is True

    @patch('requests.get')
    def test_test_connection_failure(self, mock_get, client):
        """Testa falha de conexão."""
        mock_get.side_effect = Exception("Connection failed")
        
        result = client.test_connection()
        
        assert result is False
