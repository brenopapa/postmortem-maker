"""
Cliente para a API do Jira.
Responsável por buscar informações de issues do Jira.
"""

import re
from datetime import datetime
from typing import Optional
import requests
from requests.auth import HTTPBasicAuth

from .config import JiraConfig
from .models import JiraIssue


class JiraClient:
    """Cliente para interação com a API do Jira."""

    def __init__(self, config: JiraConfig):
        """
        Inicializa o cliente do Jira.
        
        Args:
            config: Configurações do Jira.
        """
        self.config = config
        self.base_url = config.base_url.rstrip("/")
        self.auth = HTTPBasicAuth(config.email, config.api_token)
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        # Tenta detectar a versão da API disponível
        self._api_version = "3"  # Padrão é v3

    def _make_request(
        self, 
        endpoint: str, 
        params: Optional[dict] = None,
        api_version: Optional[str] = None
    ) -> dict:
        """
        Faz uma requisição GET para a API do Jira.
        Tenta API v3 primeiro, depois v2 como fallback.
        
        Args:
            endpoint: Endpoint da API.
            params: Parâmetros da query string.
            api_version: Versão da API (None = usa a detectada).
            
        Returns:
            Resposta da API em formato JSON.
            
        Raises:
            requests.exceptions.HTTPError: Se a requisição falhar.
        """
        version = api_version or self._api_version
        url = f"{self.base_url}/rest/api/{version}/{endpoint}"
        
        response = requests.get(
            url,
            auth=self.auth,
            headers=self.headers,
            params=params,
            timeout=30
        )
        
        # Se falhou com v3, tenta v2
        if response.status_code == 404 and version == "3" and api_version is None:
            self._api_version = "2"
            url_v2 = f"{self.base_url}/rest/api/2/{endpoint}"
            response = requests.get(
                url_v2,
                auth=self.auth,
                headers=self.headers,
                params=params,
                timeout=30
            )
        
        # Se ainda falhou, fornece mensagem de erro mais detalhada
        if response.status_code == 404:
            raise Exception(
                f"Issue não encontrada (404). Possíveis causas:\n"
                f"   - A issue não existe ou foi deletada\n"
                f"   - Seu token não tem permissão para acessar este projeto\n"
                f"   - O projeto pode estar restrito\n"
                f"   URL tentada: {response.url}"
            )
        elif response.status_code == 401:
            raise Exception(
                f"Autenticação falhou (401). Verifique:\n"
                f"   - JIRA_EMAIL está correto\n"
                f"   - JIRA_API_TOKEN é válido e não expirou\n"
                f"   - O token foi criado em: https://id.atlassian.com/manage-profile/security/api-tokens"
            )
        elif response.status_code == 403:
            raise Exception(
                f"Acesso negado (403). Seu usuário não tem permissão para acessar esta issue."
            )
        
        response.raise_for_status()
        return response.json()

    def extract_issue_key_from_url(self, url: str) -> Optional[str]:
        """
        Extrai a chave da issue a partir de uma URL do Jira.
        
        Args:
            url: URL da issue do Jira.
            
        Returns:
            Chave da issue ou None se não encontrada.
        """
        # Padrões comuns de URL do Jira
        patterns = [
            r"/browse/([A-Z]+-\d+)",  # https://company.atlassian.net/browse/PROJ-123
            r"/issues/([A-Z]+-\d+)",  # https://company.atlassian.net/issues/PROJ-123
            r"selectedIssue=([A-Z]+-\d+)",  # Query string
            r"([A-Z]+-\d+)$"  # Apenas a chave no final
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None

    def _parse_datetime(self, date_string: Optional[str]) -> Optional[datetime]:
        """
        Converte uma string de data do Jira para datetime.
        
        Args:
            date_string: String de data no formato ISO.
            
        Returns:
            Objeto datetime ou None se a string for inválida.
        """
        if not date_string:
            return None
        
        try:
            # Remove timezone info para simplificar
            # Formato: 2024-01-15T10:30:00.000+0000
            if "." in date_string:
                date_string = date_string.split(".")[0]
            elif "+" in date_string:
                date_string = date_string.split("+")[0]
            elif date_string.endswith("Z"):
                date_string = date_string[:-1]
            
            return datetime.fromisoformat(date_string)
        except (ValueError, AttributeError):
            return None

    def _extract_text_from_adf(self, adf_content: dict) -> str:
        """
        Extrai texto puro de um documento ADF (Atlassian Document Format).
        
        Args:
            adf_content: Conteúdo em formato ADF.
            
        Returns:
            Texto extraído.
        """
        if not adf_content:
            return ""
        
        def extract_text(node: dict) -> str:
            if not isinstance(node, dict):
                return str(node) if node else ""
            
            text_parts = []
            
            # Texto direto
            if node.get("type") == "text":
                text_parts.append(node.get("text", ""))
            
            # Links
            if node.get("type") == "inlineCard":
                text_parts.append(node.get("attrs", {}).get("url", ""))
            
            # Menções
            if node.get("type") == "mention":
                text_parts.append(f"@{node.get('attrs', {}).get('text', '')}")
            
            # Recursivamente processar conteúdo filho
            if "content" in node:
                for child in node.get("content", []):
                    text_parts.append(extract_text(child))
            
            return " ".join(filter(None, text_parts))
        
        return extract_text(adf_content).strip()

    def _get_user_display_name(self, user_data: Optional[dict]) -> str:
        """
        Extrai o nome de exibição do usuário.
        
        Args:
            user_data: Dados do usuário do Jira.
            
        Returns:
            Nome de exibição ou "Desconhecido".
        """
        if not user_data:
            return "Desconhecido"
        return user_data.get("displayName", user_data.get("name", "Desconhecido"))

    def get_issue(self, issue_key: str) -> JiraIssue:
        """
        Busca uma issue do Jira pelo seu identificador.
        Usa o endpoint /search/jql para maior compatibilidade.
        
        Args:
            issue_key: Chave da issue (ex: PROJ-123).
            
        Returns:
            Objeto JiraIssue com os dados da issue.
            
        Raises:
            Exception: Se a requisição falhar ou issue não for encontrada.
        """
        # Usa endpoint search/jql que é mais compatível
        jql = f"Key={issue_key}"
        
        try:
            data = self._make_request(
                "search/jql",
                params={
                    "jql": jql,
                    "fields": "summary,description,status,created,updated,resolutiondate,assignee,reporter,comment",
                    "expand": "changelog"
                }
            )
        except Exception:
            # Fallback para endpoint search (sem /jql)
            data = self._make_request(
                "search",
                params={
                    "jql": jql,
                    "fields": "summary,description,status,created,updated,resolutiondate,assignee,reporter,comment",
                    "expand": "changelog"
                }
            )
        
        issues = data.get("issues", [])
        if not issues:
            raise Exception(
                f"Issue {issue_key} não encontrada.\n"
                f"   Verifique se a issue existe e se você tem permissão para acessá-la."
            )
        
        issue_data = issues[0]
        fields = issue_data.get("fields", {})
        
        # Extrai descrição
        description = ""
        if fields.get("description"):
            description = self._extract_text_from_adf(fields["description"])
        
        # Extrai comentários (filtra automações)
        comments = []
        comment_data = fields.get("comment", {}).get("comments", [])
        
        # Lista de autores de automação a serem ignorados
        automation_authors = [
            "automation for jira",
            "jira automation",
            "jira service management",
            "jira software",
            "atlassian automation",
            "yoda",
        ]
        
        for comment in comment_data:
            author = self._get_user_display_name(comment.get("author"))
            
            # Ignora comentários de automação
            if author.lower() in automation_authors:
                continue
            
            body = ""
            if comment.get("body"):
                body = self._extract_text_from_adf(comment["body"])
            
            comments.append({
                "id": comment.get("id"),
                "author": author,
                "body": body,
                "created": self._parse_datetime(comment.get("created")),
                "updated": self._parse_datetime(comment.get("updated"))
            })
        
        # Monta URL da issue
        issue_url = f"{self.base_url}/browse/{issue_key}"
        
        return JiraIssue(
            key=issue_key,
            summary=fields.get("summary", ""),
            description=description,
            status=fields.get("status", {}).get("name", "Desconhecido"),
            created=self._parse_datetime(fields.get("created")) or datetime.now(),
            updated=self._parse_datetime(fields.get("updated")) or datetime.now(),
            resolved=self._parse_datetime(fields.get("resolutiondate")),
            assignee=self._get_user_display_name(fields.get("assignee")),
            reporter=self._get_user_display_name(fields.get("reporter")),
            comments=comments,
            url=issue_url,
            custom_fields={}
        )

    def get_issue_from_url(self, url: str) -> Optional[JiraIssue]:
        """
        Busca uma issue do Jira a partir de sua URL.
        
        Args:
            url: URL da issue do Jira.
            
        Returns:
            Objeto JiraIssue ou None se a URL for inválida.
        """
        issue_key = self.extract_issue_key_from_url(url)
        if not issue_key:
            return None
        
        return self.get_issue(issue_key)

    def get_issue_transitions(self, issue_key: str) -> list[dict]:
        """
        Busca o histórico de transições de uma issue.
        
        Args:
            issue_key: Chave da issue.
            
        Returns:
            Lista de transições.
        """
        data = self._make_request(
            f"issue/{issue_key}",
            params={"expand": "changelog"}
        )
        
        transitions = []
        changelog = data.get("changelog", {})
        
        for history in changelog.get("histories", []):
            for item in history.get("items", []):
                if item.get("field") == "status":
                    transitions.append({
                        "timestamp": self._parse_datetime(history.get("created")),
                        "author": self._get_user_display_name(history.get("author")),
                        "from_status": item.get("fromString"),
                        "to_status": item.get("toString")
                    })
        
        return transitions

    def search_issues(self, jql: str, max_results: int = 50) -> list[JiraIssue]:
        """
        Busca issues usando JQL (Jira Query Language).
        
        Args:
            jql: Query JQL.
            max_results: Número máximo de resultados.
            
        Returns:
            Lista de issues encontradas.
        """
        data = self._make_request(
            "search",
            params={
                "jql": jql,
                "maxResults": max_results,
                "expand": "comments",
                "fields": "*all"
            }
        )
        
        issues = []
        for issue_data in data.get("issues", []):
            fields = issue_data.get("fields", {})
            key = issue_data.get("key", "")
            
            description = ""
            if fields.get("description"):
                description = self._extract_text_from_adf(fields["description"])
            
            issues.append(JiraIssue(
                key=key,
                summary=fields.get("summary", ""),
                description=description,
                status=fields.get("status", {}).get("name", ""),
                created=self._parse_datetime(fields.get("created")) or datetime.now(),
                updated=self._parse_datetime(fields.get("updated")) or datetime.now(),
                resolved=self._parse_datetime(fields.get("resolutiondate")),
                assignee=self._get_user_display_name(fields.get("assignee")),
                reporter=self._get_user_display_name(fields.get("reporter")),
                comments=[],
                url=f"{self.base_url}/browse/{key}"
            ))
        
        return issues

    def test_connection(self) -> bool:
        """
        Testa a conexão com o Jira.
        
        Returns:
            True se a conexão for bem sucedida, False caso contrário.
        """
        try:
            self._make_request("myself")
            return True
        except Exception:
            # Tenta v2 se v3 falhou
            try:
                self._api_version = "2"
                self._make_request("myself")
                return True
            except Exception:
                return False

    def get_connection_info(self) -> dict:
        """
        Retorna informações detalhadas sobre a conexão.
        
        Returns:
            Dicionário com status e informações do usuário.
        """
        try:
            user_info = self._make_request("myself")
            return {
                "connected": True,
                "api_version": self._api_version,
                "user": user_info.get("displayName", user_info.get("name", "Unknown")),
                "email": user_info.get("emailAddress", ""),
                "account_id": user_info.get("accountId", "")
            }
        except Exception as e:
            return {
                "connected": False,
                "error": str(e)
            }
