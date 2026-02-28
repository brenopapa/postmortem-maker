"""
Cliente para a API do Notion.
Responsável por criar e atualizar páginas no Notion.
"""

from datetime import datetime
from typing import Optional
import requests

from .config import NotionConfig
from .models import Postmortem


class NotionClient:
    """Cliente para interação com a API do Notion."""

    BASE_URL = "https://api.notion.com/v1"
    NOTION_VERSION = "2022-06-28"

    def __init__(self, config: NotionConfig):
        """
        Inicializa o cliente do Notion.
        
        Args:
            config: Configurações do Notion.
        """
        self.config = config
        self.api_token = config.api_token
        self.database_id = config.database_id

    def _get_headers(self) -> dict:
        """Retorna os headers para requisições à API."""
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Notion-Version": self.NOTION_VERSION
        }

    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[dict] = None
    ) -> dict:
        """
        Faz uma requisição para a API do Notion.
        
        Args:
            method: Método HTTP.
            endpoint: Endpoint da API.
            data: Dados da requisição.
            
        Returns:
            Resposta da API em formato JSON.
        """
        url = f"{self.BASE_URL}/{endpoint}"
        
        response = requests.request(
            method,
            url,
            headers=self._get_headers(),
            json=data,
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    def _text_to_rich_text(self, text: str) -> list[dict]:
        """
        Converte texto simples para formato rich_text do Notion.
        
        Args:
            text: Texto simples.
            
        Returns:
            Lista de objetos rich_text.
        """
        return [{"type": "text", "text": {"content": text}}]

    def _markdown_to_blocks(self, markdown: str) -> list[dict]:
        """
        Converte Markdown para blocos do Notion.
        Esta é uma implementação simplificada.
        
        Args:
            markdown: Texto em Markdown.
            
        Returns:
            Lista de blocos do Notion.
        """
        blocks = []
        lines = markdown.split("\n")
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Heading 1
            if line.startswith("# "):
                blocks.append({
                    "type": "heading_1",
                    "heading_1": {
                        "rich_text": self._text_to_rich_text(line[2:])
                    }
                })
            
            # Heading 2
            elif line.startswith("## "):
                blocks.append({
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": self._text_to_rich_text(line[3:].strip("*"))
                    }
                })
            
            # Heading 3
            elif line.startswith("### "):
                blocks.append({
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": self._text_to_rich_text(line[4:])
                    }
                })
            
            # Lista com bullet
            elif line.startswith("- "):
                blocks.append({
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": self._text_to_rich_text(line[2:])
                    }
                })
            
            # Tabela (simplificado - Notion tem suporte limitado via API)
            elif line.startswith("|"):
                # Pula header separator
                if line.startswith("| ---"):
                    i += 1
                    continue
                
                # Trata como parágrafo por enquanto
                cells = [c.strip() for c in line.split("|")[1:-1]]
                if cells:
                    blocks.append({
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": self._text_to_rich_text(" | ".join(cells))
                        }
                    })
            
            # Link
            elif line.startswith("[") and "](" in line:
                # Extrai texto e URL
                import re
                match = re.match(r'\[([^\]]+)\]\(([^)]+)\)', line)
                if match:
                    text, url = match.groups()
                    blocks.append({
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{
                                "type": "text",
                                "text": {
                                    "content": text,
                                    "link": {"url": url}
                                }
                            }]
                        }
                    })
            
            # Parágrafo normal
            elif line.strip():
                # Remove formatação **bold**
                clean_line = line.replace("**", "")
                blocks.append({
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": self._text_to_rich_text(clean_line)
                    }
                })
            
            i += 1
        
        return blocks

    def create_page(
        self, 
        postmortem: Postmortem,
        parent_page_id: Optional[str] = None,
        database_id: Optional[str] = None
    ) -> dict:
        """
        Cria uma página no Notion com o postmortem.
        
        Args:
            postmortem: Objeto Postmortem.
            parent_page_id: ID da página pai (opcional).
            database_id: ID do database (opcional).
            
        Returns:
            Dados da página criada.
        """
        from .output_formatter import MarkdownFormatter
        from .config import OutputConfig
        
        # Formata o conteúdo
        formatter = MarkdownFormatter(OutputConfig())
        markdown_content = formatter.format(postmortem)
        
        # Converte para blocos do Notion
        blocks = self._markdown_to_blocks(markdown_content)
        
        # Define parent
        if database_id or self.database_id:
            parent = {
                "type": "database_id",
                "database_id": database_id or self.database_id
            }
            # Propriedades para database
            properties = {
                "Name": {
                    "title": self._text_to_rich_text(postmortem.title)
                }
            }
        elif parent_page_id:
            parent = {
                "type": "page_id",
                "page_id": parent_page_id
            }
            properties = {
                "title": {
                    "title": self._text_to_rich_text(postmortem.title)
                }
            }
        else:
            raise ValueError("É necessário fornecer parent_page_id ou database_id")
        
        # Cria a página
        data = {
            "parent": parent,
            "properties": properties,
            "children": blocks[:100]  # Notion tem limite de 100 blocos por request
        }
        
        result = self._make_request("POST", "pages", data)
        
        # Se tiver mais blocos, adiciona em batches
        if len(blocks) > 100:
            page_id = result["id"]
            for i in range(100, len(blocks), 100):
                self._make_request(
                    "PATCH",
                    f"blocks/{page_id}/children",
                    {"children": blocks[i:i+100]}
                )
        
        return result

    def test_connection(self) -> bool:
        """
        Testa a conexão com o Notion.
        
        Returns:
            True se a conexão for bem sucedida.
        """
        try:
            self._make_request("GET", "users/me")
            return True
        except Exception:
            return False
