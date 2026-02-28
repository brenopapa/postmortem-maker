#!/usr/bin/env python3
"""
Exemplo de uso do Postmortem Maker via código Python.
Este script demonstra como usar a biblioteca programaticamente.
"""

from datetime import datetime
from src.config import get_config
from src.postmortem_generator import PostmortemGenerator
from src.output_formatter import get_formatter
from src.models import TimelineEvent, ActionItem, EventSource


def main():
    """Exemplo de geração de postmortem."""
    
    # Carrega configurações do .env
    config = get_config()
    
    # Cria o gerador
    generator = PostmortemGenerator(config)
    
    # URLs de exemplo (substitua pelas suas)
    jira_urls = [
        "https://sua-empresa.atlassian.net/browse/PROJ-123",
        "https://sua-empresa.atlassian.net/browse/PROJ-456",
    ]
    
    slack_urls = [
        "https://sua-empresa.slack.com/archives/C01234567/p1234567890123456",
    ]
    
    # Gera o postmortem
    postmortem = generator.generate(
        title="PROJ - Serviço X indisponível por timeout no banco",
        incident_issue_url="https://sua-empresa.atlassian.net/browse/INC-789",
        jira_urls=jira_urls,
        slack_urls=slack_urls,
        customer_impact="Serviço completamente indisponível para todos os clientes",
        start_time=datetime(2026, 2, 18, 21, 25),
        end_time=datetime(2026, 2, 19, 13, 54),
        additional_context="""
        O deploy da versão 2.3.0 foi realizado às 21:00.
        A nova versão incluía uma query otimizada que acabou gerando deadlocks.
        """,
        use_ai=True  # Usa IA para análise se disponível
    )
    
    # Adiciona eventos manuais à linha do tempo (se necessário)
    generator.add_manual_timeline_event(
        postmortem,
        timestamp=datetime(2026, 2, 18, 21, 0),
        actor="DevOps Team",
        description="Deploy da versão 2.3.0 em produção"
    )
    
    # Adiciona itens de ação manuais
    generator.add_action_item(
        postmortem,
        action="Implementar circuit breaker para o banco de dados",
        responsible="Time de Infraestrutura",
        issues=["INFRA-100"]
    )
    
    # Formata e salva
    formatter = get_formatter(config.output)
    filepath = formatter.save(postmortem)
    
    print(f"\n✅ Postmortem salvo em: {filepath}")
    
    # Imprime preview
    print("\n" + "="*60)
    print("PREVIEW DO POSTMORTEM")
    print("="*60 + "\n")
    print(formatter.format(postmortem))


def example_with_manual_data():
    """
    Exemplo de criação de postmortem com dados manuais
    (sem consultar APIs do Jira/Slack).
    """
    from src.models import Postmortem
    from src.config import OutputConfig
    from src.output_formatter import MarkdownFormatter
    
    # Cria postmortem manualmente
    postmortem = Postmortem(
        title="Task de provisionamento BigQuery em Loop",
        incident_issue_url="https://sua-empresa.atlassian.net/browse/INC-123",
        start_time=datetime(2026, 2, 18, 21, 25),
        end_time=datetime(2026, 2, 19, 13, 54),
        duration="16h29min",
        customer_impact="Tabela indisponível para uso",
        timeline=[
            TimelineEvent(
                timestamp=datetime(2026, 2, 18, 21, 25),
                actor="Usuário",
                description="Início do reprovisionamento da tabela de staging.",
                source=EventSource.JIRA
            ),
            TimelineEvent(
                timestamp=datetime(2026, 2, 19, 9, 27),
                actor="Engenheiro de Suporte",
                description="Identificou o problema de que a task de provisionamento parcial estava travada",
                source=EventSource.SLACK
            ),
            TimelineEvent(
                timestamp=datetime(2026, 2, 19, 9, 55),
                actor="Engenheiro de Desenvolvimento",
                description="Identificação da causa do problema",
                source=EventSource.SLACK
            ),
            TimelineEvent(
                timestamp=datetime(2026, 2, 19, 13, 54),
                actor="Engenheiro de Desenvolvimento",
                description="Deployment da correção em produção",
                source=EventSource.JIRA
            ),
            TimelineEvent(
                timestamp=datetime(2026, 2, 19, 14, 4),
                actor="Engenheiro de Suporte",
                description="Confirmação de que o problema foi resolvido",
                source=EventSource.SLACK
            ),
        ],
        root_cause="""Quando a integração com a plataforma de destino está habilitada, o processo de provisionamento propaga eventos contendo o schema atualizado das tabelas que sofreram alterações. Para garantir que essas mudanças tenham sido efetivamente materializadas na plataforma, existe uma etapa de validação. Nessa etapa, são realizadas chamadas cíclicas a um endpoint da plataforma de destino para comparar:

- o schema atual da tabela na plataforma de destino
- com o schema esperado (enviado previamente via evento)

O provisionamento permanece nessa etapa até que todas as tabelas afetadas estejam atualizadas.

Na implementação inicial da integração, a plataforma de destino não persistia colunas de metadados iniciadas por underscore, como `_ingestionDatetime` e `_extraAttributes`. Como consequência, o schema materializado nunca seria idêntico ao schema enviado nos eventos. Para viabilizar a comparação, essas colunas passaram a ser explicitamente ignoradas durante a validação.

Posteriormente, a plataforma de destino passou a materializar essas colunas de metadados nas tabelas de baixa latência e a incluí-las no schema retornado pelo endpoint de consulta. Com isso, a lógica de comparação, que continuava ignorando essas colunas apenas de um lado, deixou de ser compatível com a nova resposta da API. O resultado foi a impossibilidade de obter correspondência entre os schemas, fazendo com que o processo de provisionamento permanecesse indefinidamente em loop.

Embora o deployment dessa mudança em produção tenha ocorrido há algumas semanas, o problema só foi identificado posteriormente, pois até então não havia ocorrido reprovisionamento envolvendo tabelas de baixa latência. Apenas uma tabela, pertencente a um único cliente, foi impactada por esse problema.""",
        root_cause_key_points=[
            "Alteração na resposta do endpoint de consulta de schema, decorrente de uma mudança na plataforma de destino",
            "Reprovisionamento com tabela de baixa latência entrou em loop devido à incompatibilidade na lógica de comparação de schemas"
        ],
        resolution_process="""Para tornar o processo resiliente a futuras mudanças no endpoint, a lógica de comparação foi ajustada para ignorar as colunas de metadados `_ingestionDatetime` e `_extraAttributes` em ambos os lados da comparação:

- no schema retornado pela resposta do endpoint
- no schema esperado, previamente enviado via evento

Dessa forma, a validação passa a considerar apenas as colunas efetivamente relevantes para materialização, evitando loops causados por diferenças em metadados.""",
        improvement_suggestions=[
            "Implementar testes de integração entre sistemas, pois testes unitários e testes automatizados isolados não são suficientes para detectar inconsistências decorrentes de mudanças em contratos entre sistemas.",
            "Breaking changes nas respostas de endpoints devem ser disponibilizadas em uma nova versão da API, garantindo retrocompatibilidade e evitando impacto em integrações existentes.",
        ],
        action_items=[
            ActionItem(
                action="Mudanças que possam impactar outros times devem ser devidamente comunicadas",
                responsible="Todos os times envolvidos",
                issues=["Mudança de processo"]
            )
        ]
    )
    
    # Formata e salva
    config = OutputConfig(output_dir="./output")
    formatter = MarkdownFormatter(config)
    filepath = formatter.save(postmortem, "postmortem_exemplo_manual.md")
    
    print(f"\n✅ Postmortem salvo em: {filepath}")
    
    # Imprime resultado
    print("\n" + "="*60)
    print(formatter.format(postmortem))


if __name__ == "__main__":
    # Descomente a função que deseja executar:
    
    # Exemplo com APIs (requer configuração do .env)
    # main()
    
    # Exemplo com dados manuais (não requer APIs)
    example_with_manual_data()
