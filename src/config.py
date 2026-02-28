"""
Módulo de configuração para o Postmortem Maker.
Carrega variáveis de ambiente e fornece configurações para toda a aplicação.
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()


@dataclass
class JiraConfig:
    """Configurações para a API do Jira."""
    base_url: str
    email: str
    api_token: str

    @classmethod
    def from_env(cls) -> "JiraConfig":
        """Cria configuração a partir de variáveis de ambiente."""
        return cls(
            base_url=os.getenv("JIRA_BASE_URL", ""),
            email=os.getenv("JIRA_EMAIL", ""),
            api_token=os.getenv("JIRA_API_TOKEN", "")
        )

    def is_valid(self) -> bool:
        """Verifica se a configuração é válida."""
        return all([self.base_url, self.email, self.api_token])


@dataclass
class SlackConfig:
    """Configurações para a API do Slack."""
    bot_token: str
    user_token: Optional[str] = None

    @classmethod
    def from_env(cls) -> "SlackConfig":
        """Cria configuração a partir de variáveis de ambiente."""
        return cls(
            bot_token=os.getenv("SLACK_BOT_TOKEN", ""),
            user_token=os.getenv("SLACK_USER_TOKEN")
        )

    def is_valid(self) -> bool:
        """Verifica se a configuração é válida."""
        return bool(self.bot_token)


@dataclass
class NotionConfig:
    """Configurações para a API do Notion."""
    api_token: str
    database_id: Optional[str] = None

    @classmethod
    def from_env(cls) -> "NotionConfig":
        """Cria configuração a partir de variáveis de ambiente."""
        return cls(
            api_token=os.getenv("NOTION_API_TOKEN", ""),
            database_id=os.getenv("NOTION_DATABASE_ID")
        )

    def is_valid(self) -> bool:
        """Verifica se a configuração é válida."""
        return bool(self.api_token)


@dataclass
class OpenAIConfig:
    """Configurações para a API da OpenAI."""
    api_key: str
    model: str = "gpt-4o"

    @classmethod
    def from_env(cls) -> "OpenAIConfig":
        """Cria configuração a partir de variáveis de ambiente."""
        return cls(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model=os.getenv("OPENAI_MODEL", "gpt-4o")
        )

    def is_valid(self) -> bool:
        """Verifica se a configuração é válida."""
        return bool(self.api_key)


@dataclass
class OutputConfig:
    """Configurações para a saída do postmortem."""
    output_dir: str = "./output"
    output_format: str = "markdown"

    @classmethod
    def from_env(cls) -> "OutputConfig":
        """Cria configuração a partir de variáveis de ambiente."""
        return cls(
            output_dir=os.getenv("OUTPUT_DIR", "./output"),
            output_format=os.getenv("OUTPUT_FORMAT", "markdown")
        )


@dataclass
class AppConfig:
    """Configuração completa da aplicação."""
    jira: JiraConfig
    slack: SlackConfig
    notion: NotionConfig
    openai: OpenAIConfig
    output: OutputConfig

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Cria configuração completa a partir de variáveis de ambiente."""
        return cls(
            jira=JiraConfig.from_env(),
            slack=SlackConfig.from_env(),
            notion=NotionConfig.from_env(),
            openai=OpenAIConfig.from_env(),
            output=OutputConfig.from_env()
        )

    def validate(self) -> list[str]:
        """
        Valida as configurações e retorna lista de erros.
        
        Returns:
            Lista de mensagens de erro. Lista vazia se tudo estiver válido.
        """
        errors = []
        
        if not self.jira.is_valid():
            errors.append(
                "Configuração do Jira incompleta. Verifique JIRA_BASE_URL, "
                "JIRA_EMAIL e JIRA_API_TOKEN."
            )
        
        if not self.slack.is_valid():
            errors.append(
                "Configuração do Slack incompleta. Verifique SLACK_BOT_TOKEN."
            )
        
        return errors


def get_config() -> AppConfig:
    """Retorna a configuração da aplicação."""
    return AppConfig.from_env()
