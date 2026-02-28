"""
Testes para os modelos de dados.
"""

import pytest
from datetime import datetime, timedelta

from src.models import (
    TimelineEvent,
    JiraIssue,
    SlackMessage,
    SlackThread,
    ActionItem,
    Postmortem,
    EventSource
)


class TestTimelineEvent:
    """Testes para TimelineEvent."""

    def test_creation(self):
        """Testa criação de evento."""
        event = TimelineEvent(
            timestamp=datetime(2026, 2, 18, 21, 25),
            actor="João Silva",
            description="Identificou o problema",
            source=EventSource.SLACK
        )
        
        assert event.actor == "João Silva"
        assert event.source == EventSource.SLACK
        assert event.source_url is None

    def test_to_dict(self):
        """Testa conversão para dicionário."""
        event = TimelineEvent(
            timestamp=datetime(2026, 2, 18, 21, 25),
            actor="João Silva",
            description="Identificou o problema",
            source=EventSource.JIRA,
            source_url="https://jira.example.com/browse/PROJ-123"
        )
        
        result = event.to_dict()
        
        assert result["actor"] == "João Silva"
        assert result["source"] == "jira"
        assert "2026-02-18" in result["timestamp"]


class TestJiraIssue:
    """Testes para JiraIssue."""

    def test_get_timeline_events(self):
        """Testa extração de eventos da linha do tempo."""
        issue = JiraIssue(
            key="PROJ-123",
            summary="Bug crítico",
            description="Descrição do bug",
            status="Done",
            created=datetime(2026, 2, 18, 21, 0),
            updated=datetime(2026, 2, 19, 14, 0),
            resolved=datetime(2026, 2, 19, 13, 0),
            assignee="Maria Santos",
            reporter="João Silva",
            comments=[
                {
                    "author": "Pedro Oliveira",
                    "body": "Encontrei a causa",
                    "created": datetime(2026, 2, 19, 9, 0)
                }
            ],
            url="https://jira.example.com/browse/PROJ-123"
        )
        
        events = issue.get_timeline_events()
        
        assert len(events) == 3  # criação, comentário, resolução
        assert events[0].actor == "João Silva"  # reporter na criação
        assert any(e.actor == "Pedro Oliveira" for e in events)


class TestSlackMessage:
    """Testes para SlackMessage."""

    def test_to_timeline_event(self):
        """Testa conversão para evento da linha do tempo."""
        message = SlackMessage(
            timestamp=datetime(2026, 2, 19, 9, 27),
            user_id="U12345",
            user_name="Breno",
            text="Identificou o problema",
            channel_id="C12345",
            channel_name="incidents"
        )
        
        event = message.to_timeline_event()
        
        assert event.actor == "Breno"
        assert event.source == EventSource.SLACK
        assert "problema" in event.description


class TestSlackThread:
    """Testes para SlackThread."""

    def test_get_timeline_events(self):
        """Testa extração de eventos da thread."""
        thread = SlackThread(
            channel_id="C12345",
            channel_name="incidents",
            thread_ts="1234567890.123456",
            messages=[
                SlackMessage(
                    timestamp=datetime(2026, 2, 19, 9, 0),
                    user_id="U1",
                    user_name="User 1",
                    text="Msg 1",
                    channel_id="C12345",
                    channel_name="incidents"
                ),
                SlackMessage(
                    timestamp=datetime(2026, 2, 19, 9, 30),
                    user_id="U2",
                    user_name="User 2",
                    text="Msg 2",
                    channel_id="C12345",
                    channel_name="incidents"
                )
            ]
        )
        
        events = thread.get_timeline_events()
        
        assert len(events) == 2


class TestPostmortem:
    """Testes para Postmortem."""

    def test_calculate_duration(self):
        """Testa cálculo da duração."""
        postmortem = Postmortem(
            title="Teste",
            incident_issue_url="",
            start_time=datetime(2026, 2, 18, 21, 25),
            end_time=datetime(2026, 2, 19, 13, 54),
            duration=None,
            customer_impact="Impacto X",
            timeline=[]
        )
        
        duration = postmortem.calculate_duration()
        
        assert "16h" in duration
        assert "29min" in duration

    def test_calculate_duration_ongoing(self):
        """Testa duração quando incidente ainda está em andamento."""
        postmortem = Postmortem(
            title="Teste",
            incident_issue_url="",
            start_time=datetime(2026, 2, 18, 21, 25),
            end_time=None,
            duration=None,
            customer_impact="Impacto X",
            timeline=[]
        )
        
        duration = postmortem.calculate_duration()
        
        assert duration == "Em andamento"

    def test_sort_timeline(self):
        """Testa ordenação da linha do tempo."""
        postmortem = Postmortem(
            title="Teste",
            incident_issue_url="",
            start_time=datetime(2026, 2, 18, 21, 25),
            end_time=None,
            duration=None,
            customer_impact="",
            timeline=[
                TimelineEvent(
                    timestamp=datetime(2026, 2, 19, 10, 0),
                    actor="B",
                    description="Segundo",
                    source=EventSource.MANUAL
                ),
                TimelineEvent(
                    timestamp=datetime(2026, 2, 18, 21, 0),
                    actor="A",
                    description="Primeiro",
                    source=EventSource.MANUAL
                )
            ]
        )
        
        postmortem.sort_timeline()
        
        assert postmortem.timeline[0].actor == "A"
        assert postmortem.timeline[1].actor == "B"

    def test_to_dict(self):
        """Testa conversão para dicionário."""
        postmortem = Postmortem(
            title="Teste Postmortem",
            incident_issue_url="https://jira.example.com/browse/INC-1",
            start_time=datetime(2026, 2, 18, 21, 25),
            end_time=datetime(2026, 2, 19, 13, 54),
            duration="16h29min",
            customer_impact="Serviço indisponível",
            timeline=[],
            root_cause="Causa raiz do problema",
            action_items=[
                ActionItem(
                    action="Implementar teste",
                    responsible="Time Dev",
                    issues=["PROJ-100"]
                )
            ]
        )
        
        result = postmortem.to_dict()
        
        assert result["title"] == "Teste Postmortem"
        assert result["duration"] == "16h29min"
        assert len(result["action_items"]) == 1
