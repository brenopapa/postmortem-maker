"""
Testes para o formatador de saída.
"""

import pytest
from datetime import datetime
import tempfile
import os

from src.output_formatter import MarkdownFormatter, NotionFormatter, get_formatter
from src.config import OutputConfig
from src.models import (
    Postmortem,
    TimelineEvent,
    ActionItem,
    EventSource
)


class TestMarkdownFormatter:
    """Testes para MarkdownFormatter."""

    @pytest.fixture
    def formatter(self):
        """Fixture para o formatador."""
        config = OutputConfig(output_dir=tempfile.mkdtemp())
        return MarkdownFormatter(config)

    @pytest.fixture
    def sample_postmortem(self):
        """Fixture para postmortem de exemplo."""
        return Postmortem(
            title="CAPL - Task de provisionamento em Loop",
            incident_issue_url="https://jira.example.com/browse/CAPL-9011",
            start_time=datetime(2026, 2, 18, 21, 25),
            end_time=datetime(2026, 2, 19, 13, 54),
            duration="16h29min",
            customer_impact="Tabela indisponível para uso",
            timeline=[
                TimelineEvent(
                    timestamp=datetime(2026, 2, 18, 21, 25),
                    actor="Augusto Zanini",
                    description="Início do reprovisionamento da tabela",
                    source=EventSource.JIRA,
                    source_url="https://jira.example.com/browse/CAPL-9011"
                ),
                TimelineEvent(
                    timestamp=datetime(2026, 2, 19, 9, 27),
                    actor="Breno",
                    description="Identificou o problema",
                    source=EventSource.SLACK
                ),
                TimelineEvent(
                    timestamp=datetime(2026, 2, 19, 13, 54),
                    actor="Anderson",
                    description="Deployment da correção",
                    source=EventSource.JIRA
                )
            ],
            root_cause="A lógica de comparação de schemas estava incorreta.",
            root_cause_key_points=[
                "Alteração na resposta do endpoint",
                "Reprovisionamento entrou em loop"
            ],
            resolution_process="Ajustada a lógica de comparação para ignorar colunas de metadados.",
            improvement_suggestions=[
                "Implementar testes de integração",
                "Breaking changes devem ser em nova versão da API"
            ],
            action_items=[
                ActionItem(
                    action="Comunicar changes entre times",
                    responsible="Toda a tribe",
                    issues=["Mudança de processo"]
                )
            ]
        )

    def test_format_datetime(self, formatter):
        """Testa formatação de datetime."""
        dt = datetime(2026, 2, 18, 21, 25)
        result = formatter._format_datetime(dt)
        
        assert "18/02/2026" in result
        assert "21:25" in result
        assert "BRT" in result

    def test_format_datetime_none(self, formatter):
        """Testa formatação quando datetime é None."""
        result = formatter._format_datetime(None)
        
        assert result == "Não informado"

    def test_generate_timeline_table(self, formatter, sample_postmortem):
        """Testa geração da tabela de linha do tempo."""
        result = formatter._generate_timeline_table(sample_postmortem)
        
        assert "| Data e Hora |" in result
        assert "Augusto Zanini" in result
        assert "Breno" in result
        assert "Anderson" in result

    def test_generate_action_items_table(self, formatter, sample_postmortem):
        """Testa geração da tabela de plano de ação."""
        result = formatter._generate_action_items_table(sample_postmortem)
        
        assert "| Ação |" in result
        assert "Comunicar changes" in result
        assert "Toda a tribe" in result

    def test_generate_action_items_table_empty(self, formatter):
        """Testa tabela de ação vazia."""
        postmortem = Postmortem(
            title="Teste",
            incident_issue_url="",
            start_time=datetime.now(),
            end_time=None,
            duration=None,
            customer_impact="",
            timeline=[],
            action_items=[]
        )
        
        result = formatter._generate_action_items_table(postmortem)
        
        assert "|  |  |  |" in result

    def test_format_key_points(self, formatter):
        """Testa formatação de pontos importantes."""
        points = ["Ponto 1", "Ponto 2"]
        result = formatter._format_key_points(points)
        
        assert "**Pontos importantes:**" in result
        assert "- Ponto 1" in result
        assert "- Ponto 2" in result

    def test_format_key_points_empty(self, formatter):
        """Testa formatação sem pontos."""
        result = formatter._format_key_points([])
        
        assert result == ""

    def test_format_improvements(self, formatter):
        """Testa formatação de sugestões de melhoria."""
        improvements = ["Melhoria A", "Melhoria B"]
        result = formatter._format_improvements(improvements)
        
        assert "**Sugestão de melhoria 1:**" in result
        assert "Melhoria A" in result
        assert "**Sugestão de melhoria 2:**" in result

    def test_format_full_document(self, formatter, sample_postmortem):
        """Testa formatação do documento completo."""
        result = formatter.format(sample_postmortem)
        
        # Verifica seções principais
        assert "# INTERCORRÊNCIA" in result
        assert "CAPL" in result
        assert "**Data e Hora Inicial:**" in result
        assert "**Duração:** 16h29min" in result
        assert "## **Linha do Tempo" in result
        assert "## **Causa Raíz**" in result
        assert "## **Processo de Resolução**" in result
        assert "## **Oportunidades de Melhoria**" in result
        assert "## **Plano de Ação**" in result

    def test_save(self, formatter, sample_postmortem):
        """Testa salvamento do arquivo."""
        filepath = formatter.save(sample_postmortem, "test_postmortem.md")
        
        assert os.path.exists(filepath)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert "INTERCORRÊNCIA" in content
        
        # Cleanup
        os.remove(filepath)

    def test_save_auto_filename(self, formatter, sample_postmortem):
        """Testa salvamento com nome automático."""
        filepath = formatter.save(sample_postmortem)
        
        assert os.path.exists(filepath)
        assert "postmortem_" in os.path.basename(filepath)
        assert filepath.endswith(".md")
        
        # Cleanup
        os.remove(filepath)


class TestGetFormatter:
    """Testes para factory function."""

    def test_get_markdown_formatter(self):
        """Testa obtenção de formatador Markdown."""
        config = OutputConfig(output_format="markdown")
        formatter = get_formatter(config)
        
        assert isinstance(formatter, MarkdownFormatter)

    def test_get_notion_formatter(self):
        """Testa obtenção de formatador Notion."""
        config = OutputConfig(output_format="notion")
        formatter = get_formatter(config)
        
        assert isinstance(formatter, NotionFormatter)

    def test_default_is_markdown(self):
        """Testa que padrão é Markdown."""
        config = OutputConfig()
        formatter = get_formatter(config)
        
        assert isinstance(formatter, MarkdownFormatter)
