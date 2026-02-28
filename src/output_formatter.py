"""
Formatador de saída do Postmortem.
Gera o documento final em formato Markdown/Notion.
"""

import os
import re
from datetime import datetime
from typing import Optional

from .config import OutputConfig
from .models import Postmortem


class MarkdownFormatter:
    """Formatador de postmortem para Markdown."""

    def __init__(self, config: OutputConfig):
        """
        Inicializa o formatador.
        
        Args:
            config: Configurações de saída.
        """
        self.config = config
        self.output_dir = config.output_dir

    def _format_datetime(self, dt: Optional[datetime]) -> str:
        """
        Formata datetime para o padrão brasileiro.
        
        Args:
            dt: Objeto datetime.
            
        Returns:
            String formatada.
        """
        if not dt:
            return "Não informado"
        return dt.strftime("%d/%m/%Y %H:%M") + " BRT"

    def _format_duration(self, postmortem: Postmortem) -> str:
        """
        Formata a duração do incidente.
        
        Args:
            postmortem: Objeto Postmortem.
            
        Returns:
            String formatada da duração.
        """
        return postmortem.duration or postmortem.calculate_duration()

    def _generate_timeline_table(self, postmortem: Postmortem) -> str:
        """
        Gera a tabela da linha do tempo.
        
        Args:
            postmortem: Objeto Postmortem.
            
        Returns:
            Tabela em formato Markdown.
        """
        lines = [
            "| Data e Hora | Ator (Quem) | Evento |",
            "| --- | --- | --- |"
        ]
        
        for event in postmortem.timeline:
            date_str = event.timestamp.strftime("%d/%m/%Y %H:%M")
            # Limita descrição e remove quebras de linha
            description = event.description.replace("\n", " ").replace("|", "\\|")
            if len(description) > 500:
                description = description[:497] + "..."
            
            lines.append(f"| {date_str} | {event.actor} | {description} |")
        
        return "\n".join(lines)

    def _generate_action_items_table(self, postmortem: Postmortem) -> str:
        """
        Gera a tabela do plano de ação.
        
        Args:
            postmortem: Objeto Postmortem.
            
        Returns:
            Tabela em formato Markdown.
        """
        lines = [
            "| Ação | Responsável | Issue(s) |",
            "| --- | --- | --- |"
        ]
        
        if postmortem.action_items:
            for item in postmortem.action_items:
                issues = ", ".join(item.issues) if item.issues else ""
                action = item.action.replace("\n", " ").replace("|", "\\|")
                lines.append(f"| {action} | {item.responsible} | {issues} |")
        else:
            lines.append("|  |  |  |")
        
        return "\n".join(lines)

    def _format_key_points(self, points: list[str]) -> str:
        """
        Formata os pontos importantes.
        
        Args:
            points: Lista de pontos.
            
        Returns:
            Texto formatado.
        """
        if not points:
            return ""
        
        lines = ["**Pontos importantes:**", ""]
        for point in points:
            lines.append(f"- {point}")
        
        return "\n".join(lines)

    def _format_improvements(self, improvements: list[str]) -> str:
        """
        Formata as sugestões de melhoria.
        
        Args:
            improvements: Lista de sugestões.
            
        Returns:
            Texto formatado.
        """
        if not improvements:
            return ""
        
        lines = []
        for i, improvement in enumerate(improvements, 1):
            lines.append(f"**Sugestão de melhoria {i}:** {improvement}")
            lines.append("")
        
        return "\n".join(lines)

    def _extract_title_prefix(self, title: str) -> str:
        """
        Extrai o prefixo do título (ex: CAPL, REFI).
        
        Args:
            title: Título do postmortem.
            
        Returns:
            Prefixo extraído ou "INCIDENT".
        """
        match = re.search(r"([A-Z]{2,})", title)
        return match.group(1) if match else "INCIDENT"

    def format(self, postmortem: Postmortem) -> str:
        """
        Formata o postmortem em Markdown.
        
        Args:
            postmortem: Objeto Postmortem.
            
        Returns:
            Documento formatado em Markdown.
        """
        prefix = self._extract_title_prefix(postmortem.title)
        
        # Monta o documento
        doc = f"""# INTERCORRÊNCIA - {postmortem.title}

[Link para a issue de Intercorrência {postmortem.incident_issue_url.split('/')[-1] if postmortem.incident_issue_url else prefix}]({postmortem.incident_issue_url})

**Data e Hora Inicial:** {self._format_datetime(postmortem.start_time)}
**Data e Hora Final:** {self._format_datetime(postmortem.end_time)}
**Duração:** {self._format_duration(postmortem)}
**Impacto no cliente: {postmortem.customer_impact}**

## **Linha do Tempo da Intercorrência**

{self._generate_timeline_table(postmortem)}

## **Causa Raíz**

{postmortem.root_cause if postmortem.root_cause else "_A ser preenchido_"}

{self._format_key_points(postmortem.root_cause_key_points)}

## **Processo de Resolução**

{postmortem.resolution_process if postmortem.resolution_process else "_A ser preenchido_"}

## **Oportunidades de Melhoria**

{self._format_improvements(postmortem.improvement_suggestions) if postmortem.improvement_suggestions else "_A ser preenchido_"}

## **Plano de Ação**

{self._generate_action_items_table(postmortem)}

"""
        return doc

    def save(self, postmortem: Postmortem, filename: Optional[str] = None) -> str:
        """
        Salva o postmortem em um arquivo.
        
        Args:
            postmortem: Objeto Postmortem.
            filename: Nome do arquivo (opcional).
            
        Returns:
            Caminho do arquivo salvo.
        """
        # Cria diretório de saída se não existir
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Gera nome do arquivo se não fornecido
        if not filename:
            # Sanitiza o título para uso como nome de arquivo
            safe_title = re.sub(r'[^\w\s-]', '', postmortem.title)
            safe_title = re.sub(r'\s+', '_', safe_title)[:50]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"postmortem_{safe_title}_{timestamp}.md"
        
        # Formata e salva
        content = self.format(postmortem)
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return filepath


class NotionFormatter(MarkdownFormatter):
    """
    Formatador de postmortem para Notion.
    Estende o formatador Markdown com formatações específicas do Notion.
    """

    def format(self, postmortem: Postmortem) -> str:
        """
        Formata o postmortem para Notion.
        O Notion aceita Markdown com algumas particularidades.
        
        Args:
            postmortem: Objeto Postmortem.
            
        Returns:
            Documento formatado para Notion.
        """
        # O Notion aceita o mesmo formato Markdown
        # mas podemos adicionar propriedades específicas
        return super().format(postmortem)

    def get_notion_properties(self, postmortem: Postmortem) -> dict:
        """
        Retorna propriedades para criar página no Notion.
        
        Args:
            postmortem: Objeto Postmortem.
            
        Returns:
            Dicionário de propriedades do Notion.
        """
        return {
            "title": postmortem.title,
            "start_time": postmortem.start_time.isoformat() if postmortem.start_time else None,
            "end_time": postmortem.end_time.isoformat() if postmortem.end_time else None,
            "duration": postmortem.duration,
            "impact": postmortem.customer_impact,
            "status": "Draft",
            "jira_link": postmortem.incident_issue_url
        }


def get_formatter(config: OutputConfig) -> MarkdownFormatter:
    """
    Factory function para obter o formatador correto.
    
    Args:
        config: Configurações de saída.
        
    Returns:
        Instância do formatador apropriado.
    """
    if config.output_format.lower() == "notion":
        return NotionFormatter(config)
    return MarkdownFormatter(config)
