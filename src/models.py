"""
Modelos de dados para o Postmortem Maker.
Define as estruturas de dados utilizadas em toda a aplicação.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum


class EventSource(Enum):
    """Fonte do evento na linha do tempo."""
    JIRA = "jira"
    SLACK = "slack"
    MANUAL = "manual"


@dataclass
class TimelineEvent:
    """Representa um evento na linha do tempo da intercorrência."""
    timestamp: datetime
    actor: str
    description: str
    source: EventSource
    source_url: Optional[str] = None

    def to_dict(self) -> dict:
        """Converte o evento para dicionário."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "actor": self.actor,
            "description": self.description,
            "source": self.source.value,
            "source_url": self.source_url
        }


@dataclass
class JiraIssue:
    """Representa uma issue do Jira."""
    key: str
    summary: str
    description: Optional[str]
    status: str
    created: datetime
    updated: datetime
    resolved: Optional[datetime]
    assignee: Optional[str]
    reporter: Optional[str]
    comments: list[dict] = field(default_factory=list)
    url: str = ""
    custom_fields: dict = field(default_factory=dict)
    
    def get_timeline_events(self) -> list[TimelineEvent]:
        """Extrai eventos da linha do tempo a partir da issue."""
        events = []
        
        # Evento de criação da issue
        events.append(TimelineEvent(
            timestamp=self.created,
            actor=self.reporter or "Desconhecido",
            description=f"Issue {self.key} criada: {self.summary}",
            source=EventSource.JIRA,
            source_url=self.url
        ))
        
        # Eventos dos comentários
        for comment in self.comments:
            events.append(TimelineEvent(
                timestamp=comment.get("created", self.created),
                actor=comment.get("author", "Desconhecido"),
                description=comment.get("body", ""),
                source=EventSource.JIRA,
                source_url=self.url
            ))
        
        # Evento de resolução
        if self.resolved:
            events.append(TimelineEvent(
                timestamp=self.resolved,
                actor=self.assignee or "Desconhecido",
                description=f"Issue {self.key} resolvida",
                source=EventSource.JIRA,
                source_url=self.url
            ))
        
        return events


@dataclass
class SlackMessage:
    """Representa uma mensagem do Slack."""
    timestamp: datetime
    user_id: str
    user_name: str
    text: str
    channel_id: str
    channel_name: str
    thread_ts: Optional[str] = None
    permalink: Optional[str] = None
    reactions: list[dict] = field(default_factory=list)
    
    def to_timeline_event(self) -> TimelineEvent:
        """Converte a mensagem para um evento da linha do tempo."""
        return TimelineEvent(
            timestamp=self.timestamp,
            actor=self.user_name,
            description=self.text,
            source=EventSource.SLACK,
            source_url=self.permalink
        )


@dataclass
class SlackThread:
    """Representa uma thread do Slack."""
    channel_id: str
    channel_name: str
    thread_ts: str
    messages: list[SlackMessage] = field(default_factory=list)
    permalink: Optional[str] = None
    
    def get_timeline_events(self) -> list[TimelineEvent]:
        """Extrai eventos da linha do tempo a partir da thread."""
        return [msg.to_timeline_event() for msg in self.messages]


@dataclass
class ActionItem:
    """Representa uma ação do plano de ação."""
    action: str
    responsible: str
    issues: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Converte a ação para dicionário."""
        return {
            "action": self.action,
            "responsible": self.responsible,
            "issues": self.issues
        }


@dataclass
class Postmortem:
    """Representa um postmortem completo."""
    title: str
    incident_issue_url: str
    start_time: datetime
    end_time: Optional[datetime]
    duration: Optional[str]
    customer_impact: str
    timeline: list[TimelineEvent] = field(default_factory=list)
    root_cause: str = ""
    root_cause_key_points: list[str] = field(default_factory=list)
    resolution_process: str = ""
    improvement_suggestions: list[str] = field(default_factory=list)
    action_items: list[ActionItem] = field(default_factory=list)
    
    # Dados de origem
    jira_issues: list[JiraIssue] = field(default_factory=list)
    slack_threads: list[SlackThread] = field(default_factory=list)
    
    def calculate_duration(self) -> str:
        """Calcula a duração da intercorrência."""
        if not self.end_time:
            return "Em andamento"
        
        delta = self.end_time - self.start_time
        total_seconds = int(delta.total_seconds())
        
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}min")
        
        return "".join(parts) if parts else "< 1min"
    
    def sort_timeline(self) -> None:
        """Ordena a linha do tempo por timestamp."""
        self.timeline.sort(key=lambda e: e.timestamp)
    
    def to_dict(self) -> dict:
        """Converte o postmortem para dicionário."""
        return {
            "title": self.title,
            "incident_issue_url": self.incident_issue_url,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration or self.calculate_duration(),
            "customer_impact": self.customer_impact,
            "timeline": [e.to_dict() for e in self.timeline],
            "root_cause": self.root_cause,
            "root_cause_key_points": self.root_cause_key_points,
            "resolution_process": self.resolution_process,
            "improvement_suggestions": self.improvement_suggestions,
            "action_items": [a.to_dict() for a in self.action_items]
        }
