"""
Gerador de Postmortem.
Orquestra a coleta de dados e geração do documento final.
"""

from datetime import datetime
from typing import Optional

from .config import AppConfig
from .models import (
    Postmortem, 
    JiraIssue, 
    SlackThread, 
    TimelineEvent, 
    ActionItem,
    EventSource
)
from .jira_client import JiraClient
from .slack_client import SlackClient
from .ai_analyzer import AIAnalyzer


class PostmortemGenerator:
    """Gerador de documentos de postmortem."""

    def __init__(self, config: AppConfig, use_local_llm: bool = False):
        """
        Inicializa o gerador de postmortem.
        
        Args:
            config: Configurações da aplicação.
            use_local_llm: Se True, usa LLM customizado (local ou externo) em vez da OpenAI.
        """
        self.config = config
        self.jira_client = JiraClient(config.jira) if config.jira.is_valid() else None
        self.slack_client = SlackClient(config.slack) if config.slack.is_valid() else None
        self.ai_analyzer = AIAnalyzer(
            config.openai,
            local_config=config.local_llm,
            use_local=use_local_llm
        )

    def _collect_jira_data(self, jira_urls: list[str]) -> list[JiraIssue]:
        """
        Coleta dados das issues do Jira.
        
        Args:
            jira_urls: Lista de URLs de issues do Jira.
            
        Returns:
            Lista de issues coletadas.
        """
        if not self.jira_client:
            print("⚠️  Cliente Jira não configurado. Pulando coleta de issues.")
            return []
        
        issues = []
        for url in jira_urls:
            try:
                print(f"📋 Buscando issue: {url}")
                issue = self.jira_client.get_issue_from_url(url)
                if issue:
                    issues.append(issue)
                    print(f"   ✅ {issue.key}: {issue.summary[:50]}...")
                else:
                    print(f"   ❌ Não foi possível extrair issue da URL")
            except Exception as e:
                print(f"   ❌ Erro ao buscar issue: {e}")
        
        return issues

    def _collect_slack_data(self, slack_urls: list[str]) -> list[SlackThread]:
        """
        Coleta dados das threads do Slack.
        
        Args:
            slack_urls: Lista de URLs de threads do Slack.
            
        Returns:
            Lista de threads coletadas.
        """
        if not self.slack_client:
            print("⚠️  Cliente Slack não configurado. Pulando coleta de threads.")
            return []
        
        threads = []
        for url in slack_urls:
            try:
                print(f"💬 Buscando thread: {url}")
                thread = self.slack_client.get_thread_from_url(url)
                if thread:
                    threads.append(thread)
                    print(f"   ✅ #{thread.channel_name}: {len(thread.messages)} mensagens")
                else:
                    print(f"   ❌ Não foi possível extrair thread da URL")
            except Exception as e:
                print(f"   ❌ Erro ao buscar thread: {e}")
        
        return threads

    def _build_timeline(
        self, 
        jira_issues: list[JiraIssue], 
        slack_threads: list[SlackThread]
    ) -> list[TimelineEvent]:
        """
        Constrói a linha do tempo a partir dos dados coletados.
        
        Args:
            jira_issues: Issues do Jira.
            slack_threads: Threads do Slack.
            
        Returns:
            Lista de eventos ordenados por timestamp.
        """
        events = []
        
        # Eventos do Jira
        for issue in jira_issues:
            events.extend(issue.get_timeline_events())
        
        # Eventos do Slack
        for thread in slack_threads:
            events.extend(thread.get_timeline_events())
        
        # Ordena por timestamp
        events.sort(key=lambda e: e.timestamp)
        
        return events

    def _determine_incident_times(
        self,
        jira_issues: list[JiraIssue],
        slack_threads: list[SlackThread],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> tuple[datetime, Optional[datetime]]:
        """
        Determina os horários de início e fim do incidente.
        
        Prioridade para start_time (se não fornecido):
        1. Data de criação da primeira issue do Jira
        2. Timestamp da primeira mensagem do Slack
        
        Prioridade para end_time (se não fornecido):
        1. Data de resolução da issue do Jira (se resolvida)
        2. Timestamp da última mensagem do Slack
        
        Args:
            jira_issues: Lista de issues do Jira.
            slack_threads: Lista de threads do Slack.
            start_time: Horário de início fornecido.
            end_time: Horário de fim fornecido.
            
        Returns:
            Tupla (start_time, end_time).
        """
        # Determina start_time
        if not start_time:
            candidates = []
            
            # Data de criação das issues do Jira
            for issue in jira_issues:
                if issue.created:
                    candidates.append(issue.created)
            
            # Primeira mensagem de cada thread do Slack
            for thread in slack_threads:
                if thread.messages:
                    candidates.append(thread.messages[0].timestamp)
            
            if candidates:
                start_time = min(candidates)
            else:
                start_time = datetime.now()
        
        # Determina end_time
        if not end_time:
            candidates = []
            
            # Data de resolução das issues do Jira (se resolvidas)
            for issue in jira_issues:
                if issue.resolved:
                    candidates.append(issue.resolved)
            
            # Última mensagem de cada thread do Slack
            for thread in slack_threads:
                if thread.messages:
                    candidates.append(thread.messages[-1].timestamp)
            
            if candidates:
                end_time = max(candidates)
        
        return start_time, end_time

    def generate(
        self,
        title: str,
        incident_issue_url: str,
        jira_urls: list[str],
        slack_urls: list[str],
        customer_impact: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        additional_context: Optional[str] = None,
        use_ai: bool = True
    ) -> Postmortem:
        """
        Gera um postmortem completo.
        
        Args:
            title: Título do postmortem.
            incident_issue_url: URL da issue principal de intercorrência.
            jira_urls: Lista de URLs de issues do Jira relacionadas.
            slack_urls: Lista de URLs de threads do Slack relacionadas.
            customer_impact: Descrição do impacto no cliente.
            start_time: Horário de início do incidente.
            end_time: Horário de fim do incidente.
            additional_context: Contexto adicional para análise.
            use_ai: Se True, utiliza IA para análise.
            
        Returns:
            Objeto Postmortem completo.
        """
        print("\n🔍 Iniciando coleta de dados...\n")
        
        # Coleta dados
        jira_issues = self._collect_jira_data(jira_urls)
        slack_threads = self._collect_slack_data(slack_urls)
        
        print(f"\n📊 Dados coletados:")
        print(f"   - {len(jira_issues)} issues do Jira")
        print(f"   - {len(slack_threads)} threads do Slack")
        
        # Constrói linha do tempo
        print("\n📅 Construindo linha do tempo...")
        timeline = self._build_timeline(jira_issues, slack_threads)
        print(f"   - {len(timeline)} eventos na linha do tempo")
        
        # Reescreve eventos em terceira pessoa usando IA
        if use_ai and self.ai_analyzer.is_available() and timeline:
            print("   - Reescrevendo eventos em terceira pessoa...")
            timeline = self.ai_analyzer.rewrite_timeline_events(timeline)
        
        # Determina horários (baseado em criação/resolução das issues e threads)
        start_time, end_time = self._determine_incident_times(
            jira_issues, slack_threads, start_time, end_time
        )
        
        # Cria postmortem base
        postmortem = Postmortem(
            title=title,
            incident_issue_url=incident_issue_url,
            start_time=start_time,
            end_time=end_time,
            duration=None,
            customer_impact=customer_impact,
            timeline=timeline,
            jira_issues=jira_issues,
            slack_threads=slack_threads
        )
        
        # Calcula duração
        postmortem.duration = postmortem.calculate_duration()
        
        # Análise com IA
        if use_ai and self.ai_analyzer.is_available():
            llm_type = "LLM customizado" if self.ai_analyzer.use_local else "OpenAI"
            print(f"\n🤖 Analisando com IA ({llm_type})...")
            
            # Análise de causa raiz
            print("   - Analisando causa raiz...")
            root_cause_analysis = self.ai_analyzer.analyze_root_cause(
                postmortem, additional_context
            )
            postmortem.root_cause = root_cause_analysis.get("root_cause", "")
            postmortem.root_cause_key_points = root_cause_analysis.get("key_points", [])
            
            # Sugestões de melhoria
            print("   - Gerando sugestões de melhoria...")
            postmortem.improvement_suggestions = self.ai_analyzer.suggest_improvements(
                postmortem, root_cause_analysis
            )
            
            # Processo de resolução
            print("   - Descrevendo processo de resolução...")
            postmortem.resolution_process = self.ai_analyzer.generate_resolution_summary(
                postmortem, root_cause_analysis
            )
            
            # Itens de ação
            print("   - Sugerindo itens de ação...")
            action_items_data = self.ai_analyzer.suggest_action_items(
                postmortem, root_cause_analysis, postmortem.improvement_suggestions
            )
            postmortem.action_items = [
                ActionItem(
                    action=item.get("action", ""),
                    responsible=item.get("responsible", ""),
                    issues=item.get("issues", [])
                )
                for item in action_items_data
            ]
            
            print("   ✅ Análise com IA concluída")
        elif use_ai:
            print("\n⚠️  IA não disponível. Configure OPENAI_API_KEY para análise automática.")
        
        print("\n✨ Postmortem gerado com sucesso!\n")
        
        return postmortem

    def add_manual_timeline_event(
        self,
        postmortem: Postmortem,
        timestamp: datetime,
        actor: str,
        description: str
    ) -> None:
        """
        Adiciona um evento manual à linha do tempo.
        
        Args:
            postmortem: Postmortem a ser modificado.
            timestamp: Data/hora do evento.
            actor: Pessoa responsável pelo evento.
            description: Descrição do evento.
        """
        event = TimelineEvent(
            timestamp=timestamp,
            actor=actor,
            description=description,
            source=EventSource.MANUAL
        )
        postmortem.timeline.append(event)
        postmortem.sort_timeline()

    def add_action_item(
        self,
        postmortem: Postmortem,
        action: str,
        responsible: str,
        issues: Optional[list[str]] = None
    ) -> None:
        """
        Adiciona um item ao plano de ação.
        
        Args:
            postmortem: Postmortem a ser modificado.
            action: Descrição da ação.
            responsible: Responsável pela ação.
            issues: Issues relacionadas.
        """
        item = ActionItem(
            action=action,
            responsible=responsible,
            issues=issues or []
        )
        postmortem.action_items.append(item)
