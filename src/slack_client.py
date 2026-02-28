"""
Cliente para a API do Slack.
Responsável por buscar mensagens e threads do Slack.
"""

import re
from datetime import datetime
from typing import Optional
import requests

from .config import SlackConfig
from .models import SlackMessage, SlackThread


class SlackClient:
    """Cliente para interação com a API do Slack."""

    BASE_URL = "https://slack.com/api"

    def __init__(self, config: SlackConfig):
        """
        Inicializa o cliente do Slack.
        
        Args:
            config: Configurações do Slack.
        """
        self.config = config
        self.bot_token = config.bot_token
        self.user_token = config.user_token
        self._users_cache: dict[str, str] = {}
        self._channels_cache: dict[str, str] = {}

    def _get_headers(self, use_user_token: bool = False) -> dict:
        """
        Retorna os headers para a requisição.
        
        Args:
            use_user_token: Se True, usa o token de usuário ao invés do bot.
            
        Returns:
            Headers da requisição.
        """
        token = self.user_token if use_user_token and self.user_token else self.bot_token
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def _make_request(
        self, 
        endpoint: str, 
        params: Optional[dict] = None,
        use_user_token: bool = False
    ) -> dict:
        """
        Faz uma requisição GET para a API do Slack.
        
        Args:
            endpoint: Endpoint da API.
            params: Parâmetros da query string.
            use_user_token: Se True, usa o token de usuário.
            
        Returns:
            Resposta da API em formato JSON.
            
        Raises:
            Exception: Se a requisição falhar.
        """
        url = f"{self.BASE_URL}/{endpoint}"
        response = requests.get(
            url,
            headers=self._get_headers(use_user_token),
            params=params,
            timeout=30
        )
        response.raise_for_status()
        
        data = response.json()
        if not data.get("ok"):
            error = data.get("error", "Unknown error")
            raise Exception(f"Slack API error: {error}")
        
        return data

    def parse_thread_url(self, url: str) -> Optional[tuple[str, str]]:
        """
        Extrai channel_id e thread_ts de uma URL do Slack.
        
        Args:
            url: URL da thread do Slack.
            
        Returns:
            Tupla (channel_id, thread_ts) ou None se a URL for inválida.
        """
        # Padrões de URL do Slack
        patterns = [
            # https://workspace.slack.com/archives/C01234567/p1234567890123456
            r"archives/([A-Z0-9]+)/p(\d+)",
            # https://app.slack.com/client/T01234567/C01234567/thread/C01234567-1234567890.123456
            r"thread/[A-Z0-9]+-(\d+\.\d+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                if len(match.groups()) == 2:
                    channel_id = match.group(1)
                    # Converte timestamp de p1234567890123456 para 1234567890.123456
                    ts = match.group(2)
                    if len(ts) > 10:
                        thread_ts = f"{ts[:10]}.{ts[10:]}"
                    else:
                        thread_ts = ts
                    return (channel_id, thread_ts)
                elif len(match.groups()) == 1:
                    # Thread ts no formato 1234567890.123456
                    thread_ts = match.group(1)
                    # Precisa extrair channel_id de outra parte da URL
                    channel_match = re.search(r"/([A-Z][A-Z0-9]+)/thread/", url)
                    if channel_match:
                        return (channel_match.group(1), thread_ts)
        
        return None

    def _parse_slack_timestamp(self, ts: str) -> datetime:
        """
        Converte timestamp do Slack para datetime.
        
        Args:
            ts: Timestamp do Slack (formato: 1234567890.123456).
            
        Returns:
            Objeto datetime.
        """
        try:
            # Slack timestamp é Unix timestamp com microsegundos
            return datetime.fromtimestamp(float(ts))
        except (ValueError, TypeError):
            return datetime.now()

    def get_user_name(self, user_id: str) -> str:
        """
        Busca o nome de um usuário pelo ID.
        
        Args:
            user_id: ID do usuário no Slack.
            
        Returns:
            Nome do usuário ou o ID se não encontrado.
        """
        if user_id in self._users_cache:
            return self._users_cache[user_id]
        
        try:
            data = self._make_request("users.info", {"user": user_id})
            user = data.get("user", {})
            name = user.get("real_name") or user.get("name") or user_id
            self._users_cache[user_id] = name
            return name
        except Exception:
            return user_id

    def get_channel_name(self, channel_id: str) -> str:
        """
        Busca o nome de um canal pelo ID.
        
        Args:
            channel_id: ID do canal no Slack.
            
        Returns:
            Nome do canal ou o ID se não encontrado.
        """
        if channel_id in self._channels_cache:
            return self._channels_cache[channel_id]
        
        try:
            data = self._make_request("conversations.info", {"channel": channel_id})
            channel = data.get("channel", {})
            name = channel.get("name") or channel_id
            self._channels_cache[channel_id] = name
            return name
        except Exception:
            return channel_id

    def _clean_message_text(self, text: str) -> str:
        """
        Limpa e formata o texto da mensagem.
        
        Args:
            text: Texto original da mensagem.
            
        Returns:
            Texto formatado.
        """
        if not text:
            return ""
        
        # Resolve menções de usuário <@U1234567>
        def resolve_mention(match):
            user_id = match.group(1)
            return f"@{self.get_user_name(user_id)}"
        
        text = re.sub(r"<@([A-Z0-9]+)>", resolve_mention, text)
        
        # Resolve menções de canal <#C1234567|channel-name>
        text = re.sub(r"<#[A-Z0-9]+\|([^>]+)>", r"#\1", text)
        
        # Remove links formatados <http://url|label>
        text = re.sub(r"<(https?://[^|>]+)\|([^>]+)>", r"\2 (\1)", text)
        text = re.sub(r"<(https?://[^>]+)>", r"\1", text)
        
        return text.strip()

    def get_thread_messages(
        self, 
        channel_id: str, 
        thread_ts: str,
        limit: int = 100
    ) -> list[SlackMessage]:
        """
        Busca todas as mensagens de uma thread.
        
        Args:
            channel_id: ID do canal.
            thread_ts: Timestamp da mensagem pai da thread.
            limit: Número máximo de mensagens.
            
        Returns:
            Lista de mensagens da thread.
        """
        messages = []
        cursor = None
        channel_name = self.get_channel_name(channel_id)
        
        while True:
            params = {
                "channel": channel_id,
                "ts": thread_ts,
                "limit": min(limit - len(messages), 100)
            }
            if cursor:
                params["cursor"] = cursor
            
            data = self._make_request("conversations.replies", params)
            
            for msg in data.get("messages", []):
                user_id = msg.get("user", "")
                user_name = self.get_user_name(user_id) if user_id else "Bot"
                
                # Tenta obter permalink
                permalink = None
                try:
                    permalink_data = self._make_request(
                        "chat.getPermalink",
                        {"channel": channel_id, "message_ts": msg.get("ts")}
                    )
                    permalink = permalink_data.get("permalink")
                except Exception:
                    pass
                
                messages.append(SlackMessage(
                    timestamp=self._parse_slack_timestamp(msg.get("ts", "0")),
                    user_id=user_id,
                    user_name=user_name,
                    text=self._clean_message_text(msg.get("text", "")),
                    channel_id=channel_id,
                    channel_name=channel_name,
                    thread_ts=thread_ts,
                    permalink=permalink,
                    reactions=msg.get("reactions", [])
                ))
            
            # Paginação
            cursor = data.get("response_metadata", {}).get("next_cursor")
            if not cursor or len(messages) >= limit:
                break
        
        return messages

    def get_thread(self, channel_id: str, thread_ts: str) -> SlackThread:
        """
        Busca uma thread completa do Slack.
        
        Args:
            channel_id: ID do canal.
            thread_ts: Timestamp da mensagem pai da thread.
            
        Returns:
            Objeto SlackThread com todas as mensagens.
        """
        messages = self.get_thread_messages(channel_id, thread_ts)
        channel_name = self.get_channel_name(channel_id)
        
        # Pega permalink da primeira mensagem
        permalink = messages[0].permalink if messages else None
        
        return SlackThread(
            channel_id=channel_id,
            channel_name=channel_name,
            thread_ts=thread_ts,
            messages=messages,
            permalink=permalink
        )

    def get_thread_from_url(self, url: str) -> Optional[SlackThread]:
        """
        Busca uma thread a partir de sua URL.
        
        Args:
            url: URL da thread do Slack.
            
        Returns:
            Objeto SlackThread ou None se a URL for inválida.
        """
        parsed = self.parse_thread_url(url)
        if not parsed:
            return None
        
        channel_id, thread_ts = parsed
        return self.get_thread(channel_id, thread_ts)

    def search_messages(
        self, 
        query: str, 
        count: int = 20,
        sort: str = "timestamp"
    ) -> list[SlackMessage]:
        """
        Busca mensagens usando a API de pesquisa do Slack.
        Requer token de usuário com permissão search:read.
        
        Args:
            query: Termo de busca.
            count: Número máximo de resultados.
            sort: Ordenação (timestamp ou score).
            
        Returns:
            Lista de mensagens encontradas.
        """
        if not self.user_token:
            raise Exception("User token required for search")
        
        data = self._make_request(
            "search.messages",
            {"query": query, "count": count, "sort": sort},
            use_user_token=True
        )
        
        messages = []
        for match in data.get("messages", {}).get("matches", []):
            channel = match.get("channel", {})
            user_id = match.get("user", "") or match.get("username", "")
            
            messages.append(SlackMessage(
                timestamp=self._parse_slack_timestamp(match.get("ts", "0")),
                user_id=user_id,
                user_name=self.get_user_name(user_id) if user_id else "Desconhecido",
                text=self._clean_message_text(match.get("text", "")),
                channel_id=channel.get("id", ""),
                channel_name=channel.get("name", ""),
                thread_ts=match.get("thread_ts"),
                permalink=match.get("permalink")
            ))
        
        return messages

    def test_connection(self) -> bool:
        """
        Testa a conexão com o Slack.
        
        Returns:
            True se a conexão for bem sucedida, False caso contrário.
        """
        try:
            self._make_request("auth.test")
            return True
        except Exception:
            return False
