"""
Módulo de análise utilizando IA (OpenAI).
Responsável por gerar análises de causa raiz e sugestões de melhoria.
"""

from typing import Optional
import json
import re
import requests

from openai import OpenAI

from .config import OpenAIConfig, LocalLLMConfig
from .models import Postmortem, JiraIssue, SlackThread, TimelineEvent


def _extract_json(text: str) -> Optional[dict]:
    """
    Extrai JSON de um texto que pode conter markdown ou texto adicional.
    
    Args:
        text: Texto que pode conter JSON.
        
    Returns:
        Dicionário extraído ou None se não encontrar JSON válido.
    """
    if not text:
        return None
    
    text = text.strip()
    
    # Remove markdown code blocks
    if "```" in text:
        # Try to extract content between ```json and ```
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if match:
            text = match.group(1).strip()
    
    # Try to find JSON object in the text
    # Look for the first { and last }
    start_idx = text.find('{')
    end_idx = text.rfind('}')
    
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        json_str = text[start_idx:end_idx + 1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
    
    # Try parsing the whole text as JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    return None


class AIAnalyzer:
    """Analisador de postmortem utilizando IA."""

    def __init__(self, config: OpenAIConfig, local_config: Optional[LocalLLMConfig] = None, use_local: bool = False):
        """
        Inicializa o analisador de IA.
        
        Args:
            config: Configurações da OpenAI.
            local_config: Configurações do LLM customizado (local ou externo).
            use_local: Se True, usa o LLM customizado em vez da OpenAI.
        """
        self.config = config
        self.local_config = local_config
        self.use_local = use_local
        
        if use_local and local_config:
            self.client = None
            self.model = local_config.model
        else:
            self.client = OpenAI(api_key=config.api_key) if config.is_valid() else None
            self.model = config.model

    def is_available(self) -> bool:
        """Verifica se a IA está disponível."""
        if self.use_local and self.local_config:
            return self.local_config.is_valid()
        return self.client is not None

    def _call_local_llm(self, system_prompt: str, user_input: str) -> Optional[str]:
        """
        Chama o LLM customizado (local ou externo).
        
        Args:
            system_prompt: Prompt do sistema.
            user_input: Entrada do usuário.
            
        Returns:
            Resposta do modelo ou None se houver erro.
        """
        if not self.local_config:
            return None
            
        try:
            response = requests.post(
                self.local_config.base_url,
                headers={"Content-Type": "application/json"},
                json={
                    "model": self.local_config.model,
                    "system_prompt": system_prompt,
                    "input": user_input
                },
                timeout=120
            )
            response.raise_for_status()
            data = response.json()
            
            # Handle OpenAI-compatible format (LM Studio, Ollama, etc.)
            if "choices" in data and len(data["choices"]) > 0:
                choice = data["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    return choice["message"]["content"]
                if "text" in choice:
                    return choice["text"]
            
            # Handle list format: [{'type': 'message', 'content': '...'}]
            if isinstance(data, list) and len(data) > 0:
                first_item = data[0]
                if isinstance(first_item, dict) and "content" in first_item:
                    return first_item["content"]
            
            # Handle other common formats
            if isinstance(data, dict):
                if "response" in data:
                    result = data["response"]
                    # Check if response is a list with content
                    if isinstance(result, list) and len(result) > 0:
                        first_item = result[0]
                        if isinstance(first_item, dict) and "content" in first_item:
                            return first_item["content"]
                    return result if isinstance(result, str) else str(result)
                if "output" in data:
                    result = data["output"]
                    if isinstance(result, list) and len(result) > 0:
                        first_item = result[0]
                        if isinstance(first_item, dict) and "content" in first_item:
                            return first_item["content"]
                    return result if isinstance(result, str) else str(result)
                if "text" in data:
                    result = data["text"]
                    return result if isinstance(result, str) else str(result)
                if "content" in data:
                    result = data["content"]
                    return result if isinstance(result, str) else str(result)
            
            # Last resort - convert to string but try to extract content if it looks like a list
            result_str = str(data)
            # Check if it looks like [{'type': 'message', 'content': '...'}]
            if result_str.startswith("[{") and "'content':" in result_str:
                try:
                    import ast
                    parsed = ast.literal_eval(result_str)
                    if isinstance(parsed, list) and len(parsed) > 0:
                        if isinstance(parsed[0], dict) and "content" in parsed[0]:
                            return parsed[0]["content"]
                except:
                    pass
            
            return result_str
        except Exception as e:
            print(f"Erro ao chamar LLM customizado: {e}")
            return None

    def _call_llm(self, system_prompt: str, user_prompt: str, temperature: float = 0.3, max_tokens: int = 2000) -> Optional[str]:
        """
        Chama o LLM (local ou OpenAI).
        
        Args:
            system_prompt: Prompt do sistema.
            user_prompt: Prompt do usuário.
            temperature: Temperatura do modelo.
            max_tokens: Número máximo de tokens.
            
        Returns:
            Resposta do modelo ou None se houver erro.
        """
        if self.use_local:
            return self._call_local_llm(system_prompt, user_prompt)
        
        if not self.client:
            return None
            
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Erro ao chamar OpenAI: {e}")
            return None

    def _format_timeline_for_prompt(self, timeline: list[TimelineEvent]) -> str:
        """
        Formata a linha do tempo para o prompt.
        
        Args:
            timeline: Lista de eventos da linha do tempo.
            
        Returns:
            Texto formatado da linha do tempo.
        """
        lines = []
        for event in sorted(timeline, key=lambda e: e.timestamp):
            lines.append(
                f"- {event.timestamp.strftime('%d/%m/%Y %H:%M')} | "
                f"{event.actor}: {event.description[:500]}"
            )
        return "\n".join(lines)

    def _format_jira_issues_for_prompt(self, issues: list[JiraIssue]) -> str:
        """
        Formata as issues do Jira para o prompt.
        
        Args:
            issues: Lista de issues do Jira.
            
        Returns:
            Texto formatado das issues.
        """
        lines = []
        for issue in issues:
            lines.append(f"\n### {issue.key}: {issue.summary}")
            if issue.description:
                lines.append(f"Descrição: {issue.description[:1000]}")
            
            if issue.comments:
                lines.append("Comentários:")
                for comment in issue.comments[-10:]:  # Últimos 10 comentários
                    lines.append(
                        f"  - {comment.get('author')}: "
                        f"{comment.get('body', '')[:300]}"
                    )
        
        return "\n".join(lines)

    def _format_slack_threads_for_prompt(self, threads: list[SlackThread]) -> str:
        """
        Formata as threads do Slack para o prompt.
        
        Args:
            threads: Lista de threads do Slack.
            
        Returns:
            Texto formatado das threads.
        """
        lines = []
        for thread in threads:
            lines.append(f"\n### Thread no canal #{thread.channel_name}")
            for msg in thread.messages[:30]:  # Primeiras 30 mensagens
                lines.append(
                    f"  - {msg.timestamp.strftime('%d/%m/%Y %H:%M')} | "
                    f"{msg.user_name}: {msg.text[:300]}"
                )
        
        return "\n".join(lines)

    def analyze_root_cause(
        self,
        postmortem: Postmortem,
        additional_context: Optional[str] = None
    ) -> dict:
        """
        Analisa a causa raiz do incidente utilizando IA.
        
        Args:
            postmortem: Objeto Postmortem com dados coletados.
            additional_context: Contexto adicional para a análise.
            
        Returns:
            Dicionário com a análise da causa raiz.
        """
        if not self.is_available():
            return {
                "root_cause": "",
                "key_points": [],
                "confidence": 0
            }
        
        timeline_text = self._format_timeline_for_prompt(postmortem.timeline)
        jira_text = self._format_jira_issues_for_prompt(postmortem.jira_issues)
        slack_text = self._format_slack_threads_for_prompt(postmortem.slack_threads)
        
        prompt = f"""Você é um engenheiro de software sênior especializado em análise de incidentes.
Analise as informações abaixo e identifique a causa raiz do incidente.

## Informações do Incidente

**Título:** {postmortem.title}
**Impacto no cliente:** {postmortem.customer_impact}
**Início:** {postmortem.start_time.strftime('%d/%m/%Y %H:%M') if postmortem.start_time else 'Não informado'}
**Fim:** {postmortem.end_time.strftime('%d/%m/%Y %H:%M') if postmortem.end_time else 'Não informado'}

## Linha do Tempo
{timeline_text}

## Issues do Jira
{jira_text}

## Discussões no Slack
{slack_text}

{f"## Contexto Adicional{chr(10)}{additional_context}" if additional_context else ""}

## Instruções

Forneça uma análise detalhada da causa raiz em português brasileiro. A resposta deve ser em formato JSON com os seguintes campos:

{{
    "root_cause": "Descrição detalhada e técnica da causa raiz do incidente, explicando o que aconteceu e por quê. Deve ter pelo menos 3 parágrafos bem desenvolvidos.",
    "key_points": ["Lista de 2-5 pontos importantes que contribuíram para o incidente"],
    "technical_details": "Detalhes técnicos adicionais que ajudam a entender o problema"
}}

Responda APENAS com o JSON, sem markdown ou texto adicional."""

        system_prompt = "Você é um engenheiro de software sênior especializado em análise de incidentes."
        
        try:
            content = self._call_llm(system_prompt, prompt, temperature=0.3, max_tokens=2000)
            
            if not content:
                return {
                    "root_cause": "",
                    "key_points": [],
                    "technical_details": ""
                }
            
            result = _extract_json(content)
            if result:
                return result
            
            return {
                "root_cause": "",
                "key_points": [],
                "technical_details": ""
            }
        except Exception as e:
            print(f"Erro ao analisar causa raiz: {e}")
            return {
                "root_cause": "",
                "key_points": [],
                "technical_details": ""
            }

    def suggest_improvements(
        self,
        postmortem: Postmortem,
        root_cause_analysis: dict
    ) -> list[str]:
        """
        Sugere melhorias para evitar incidentes similares.
        
        Args:
            postmortem: Objeto Postmortem com dados coletados.
            root_cause_analysis: Análise da causa raiz.
            
        Returns:
            Lista de sugestões de melhoria.
        """
        if not self.is_available():
            return []
        
        prompt = f"""Você é um engenheiro de software sênior especializado em melhoria de processos.
Com base na análise do incidente abaixo, sugira oportunidades de melhoria.

## Incidente

**Título:** {postmortem.title}
**Impacto:** {postmortem.customer_impact}

## Causa Raiz

{root_cause_analysis.get('root_cause', 'Não identificada')}

## Pontos Importantes

{chr(10).join(f"- {p}" for p in root_cause_analysis.get('key_points', []))}

## Instruções

Forneça 3-5 sugestões de melhoria em português brasileiro. Cada sugestão deve:
- Ser específica e acionável
- Relacionar-se diretamente com a causa raiz ou pontos importantes
- Incluir o contexto de por que a melhoria é importante

Responda em formato JSON:
{{
    "improvements": [
        "Sugestão de melhoria 1: Descrição detalhada...",
        "Sugestão de melhoria 2: Descrição detalhada...",
        "Sugestão de melhoria 3: Descrição detalhada..."
    ]
}}

Responda APENAS com o JSON, sem markdown ou texto adicional."""

        system_prompt = "Você é um engenheiro de software sênior especializado em melhoria de processos."
        
        try:
            content = self._call_llm(system_prompt, prompt, temperature=0.5, max_tokens=1500)
            
            if not content:
                return []
            
            data = _extract_json(content)
            if data:
                return data.get("improvements", [])
            return []
        except Exception as e:
            print(f"Erro ao sugerir melhorias: {e}")
            return []

    def generate_resolution_summary(
        self,
        postmortem: Postmortem,
        root_cause_analysis: dict
    ) -> str:
        """
        Gera um resumo do processo de resolução.
        
        Args:
            postmortem: Objeto Postmortem com dados coletados.
            root_cause_analysis: Análise da causa raiz.
            
        Returns:
            Texto descrevendo o processo de resolução.
        """
        if not self.is_available():
            return ""
        
        timeline_text = self._format_timeline_for_prompt(postmortem.timeline)
        
        prompt = f"""Você é um engenheiro de software sênior escrevendo documentação de postmortem.
Descreva o processo de resolução do incidente com base nas informações abaixo.

## Incidente

**Título:** {postmortem.title}
**Causa Raiz:** {root_cause_analysis.get('root_cause', 'Não identificada')}

## Linha do Tempo
{timeline_text}

## Instruções

Escreva um resumo em português brasileiro do processo de resolução, incluindo:
- O que foi feito para resolver o problema
- Quais ações técnicas foram tomadas
- Se houver PRs ou deploys mencionados, inclua-os

Responda com apenas o texto do resumo, sem JSON ou formatação especial. 
O texto deve ter 2-3 parágrafos bem desenvolvidos."""

        system_prompt = "Você é um engenheiro de software sênior escrevendo documentação de postmortem."
        
        try:
            content = self._call_llm(system_prompt, prompt, temperature=0.3, max_tokens=1000)
            return content.strip() if content else ""
        except Exception as e:
            print(f"Erro ao gerar resumo de resolução: {e}")
            return ""

    def rewrite_timeline_events(
        self,
        timeline: list[TimelineEvent]
    ) -> list[TimelineEvent]:
        """
        Reescreve os eventos da linha do tempo em terceira pessoa.
        
        Transforma mensagens informais ou em primeira pessoa em descrições
        objetivas e profissionais em terceira pessoa.
        
        Args:
            timeline: Lista de eventos da linha do tempo.
            
        Returns:
            Lista de eventos com descrições reescritas.
        """
        if not self.is_available() or not timeline:
            return timeline
        
        # Formata os eventos para o prompt
        events_text = ""
        for i, event in enumerate(timeline):
            events_text += f"{i}. [{event.actor}]: {event.description[:500]}\n"
        
        prompt = f"""Você é um redator técnico especializado em documentação de incidentes.
Reescreva cada evento da linha do tempo abaixo em terceira pessoa, transformando
mensagens informais ou em primeira pessoa em descrições objetivas e profissionais.

## Eventos Originais

{events_text}

## Instruções

1. Reescreva cada evento em terceira pessoa, de forma objetiva
2. Remova cumprimentos, emojis, e linguagem informal
3. Remova menções a usuários (como @usuario ou <!subteam^...>)
4. Mantenha as informações técnicas relevantes (IDs, URLs, erros)
5. Seja conciso mas informativo
6. Mantenha o mesmo índice do evento original

Exemplo de transformação:
- Original: "@time, bom dia! Estamos com uma task travada. Podem dar uma olhada?"
- Reescrito: "Identificou task travada e solicitou apoio ao time responsável."

Responda em formato JSON:
{{
    "events": [
        {{"index": 0, "description": "Descrição reescrita em terceira pessoa"}},
        {{"index": 1, "description": "Descrição reescrita em terceira pessoa"}}
    ]
}}

Responda APENAS com o JSON, sem markdown ou texto adicional."""

        system_prompt = "Você é um redator técnico especializado em documentação de incidentes."
        
        try:
            content = self._call_llm(system_prompt, prompt, temperature=0.3, max_tokens=4000)
            
            if not content:
                return timeline
            
            data = _extract_json(content)
            if not data:
                return timeline
            
            rewritten_events = data.get("events", [])
            
            # Cria mapeamento de índice para nova descrição
            description_map = {
                item["index"]: item["description"]
                for item in rewritten_events
            }
            
            # Atualiza os eventos com as novas descrições
            from .models import TimelineEvent
            updated_timeline = []
            for i, event in enumerate(timeline):
                new_description = description_map.get(i, event.description)
                updated_timeline.append(TimelineEvent(
                    timestamp=event.timestamp,
                    actor=event.actor,
                    description=new_description,
                    source=event.source,
                    source_url=event.source_url
                ))
            
            return updated_timeline
            
        except Exception as e:
            print(f"Erro ao reescrever linha do tempo: {e}")
            return timeline

    def suggest_action_items(
        self,
        postmortem: Postmortem,
        root_cause_analysis: dict,
        improvements: list[str]
    ) -> list[dict]:
        """
        Sugere itens de ação para o plano de ação.
        
        Args:
            postmortem: Objeto Postmortem com dados coletados.
            root_cause_analysis: Análise da causa raiz.
            improvements: Lista de sugestões de melhoria.
            
        Returns:
            Lista de itens de ação sugeridos.
        """
        if not self.is_available():
            return []
        
        # Extrai nomes de pessoas mencionadas
        people = set()
        for event in postmortem.timeline:
            if event.actor and event.actor != "Desconhecido":
                people.add(event.actor)
        
        prompt = f"""Você é um engenheiro de software sênior planejando ações pós-incidente.
Com base no incidente e sugestões de melhoria, crie um plano de ação.

## Incidente

**Título:** {postmortem.title}

## Sugestões de Melhoria

{chr(10).join(f"- {s}" for s in improvements)}

## Pessoas Envolvidas

{chr(10).join(f"- {p}" for p in people) if people else "Não identificadas"}

## Instruções

Crie 2-4 itens de ação em português brasileiro. Cada item deve:
- Ser específico e acionável
- Ter um responsável sugerido (pode ser genérico como "Time de Desenvolvimento" ou "Squad X")
- Incluir referência a issues se relevante

Responda em formato JSON:
{{
    "action_items": [
        {{"action": "Descrição da ação", "responsible": "Responsável sugerido", "issues": ["issue1", "issue2"]}},
        {{"action": "Descrição da ação 2", "responsible": "Responsável sugerido", "issues": []}}
    ]
}}

Responda APENAS com o JSON, sem markdown ou texto adicional."""

        system_prompt = "Você é um engenheiro de software sênior planejando ações pós-incidente."
        
        try:
            content = self._call_llm(system_prompt, prompt, temperature=0.5, max_tokens=1000)
            
            if not content:
                return []
            
            data = _extract_json(content)
            if data:
                return data.get("action_items", [])
            return []
        except Exception as e:
            print(f"Erro ao sugerir ações: {e}")
            return []
