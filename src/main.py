"""
Ponto de entrada principal da aplicação.
Interface de linha de comando (CLI) para o Postmortem Maker.
"""

import argparse
import sys
from datetime import datetime
from typing import Optional

from .config import get_config, AppConfig
from .postmortem_generator import PostmortemGenerator
from .output_formatter import get_formatter
from .notion_client import NotionClient


def parse_datetime(date_str: str) -> Optional[datetime]:
    """
    Converte string de data para datetime.
    
    Args:
        date_str: String de data em formato DD/MM/YYYY HH:MM ou ISO.
        
    Returns:
        Objeto datetime ou None se inválido.
    """
    if not date_str:
        return None
    
    formats = [
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    print(f"⚠️  Formato de data não reconhecido: {date_str}")
    return None


def interactive_mode(config: AppConfig) -> None:
    """
    Modo interativo para coleta de informações do postmortem.
    
    Args:
        config: Configurações da aplicação.
    """
    print("\n" + "="*60)
    print("🔧 POSTMORTEM MAKER - Modo Interativo")
    print("="*60 + "\n")
    
    # Título
    title = input("📌 Título do postmortem: ").strip()
    if not title:
        print("❌ Título é obrigatório!")
        return
    
    # URL da issue principal
    incident_url = input("🔗 URL da issue de intercorrência (Jira): ").strip()
    
    # Impacto no cliente
    customer_impact = input("💥 Impacto no cliente: ").strip()
    if not customer_impact:
        customer_impact = "A ser determinado"
    
    # Datas
    start_str = input("📅 Data/hora inicial (DD/MM/YYYY HH:MM) [Enter para detectar]: ").strip()
    start_time = parse_datetime(start_str) if start_str else None
    
    end_str = input("📅 Data/hora final (DD/MM/YYYY HH:MM) [Enter para detectar]: ").strip()
    end_time = parse_datetime(end_str) if end_str else None
    
    # URLs do Jira
    print("\n📋 URLs das issues do Jira (uma por linha, linha vazia para terminar):")
    jira_urls = []
    while True:
        url = input("   URL: ").strip()
        if not url:
            break
        jira_urls.append(url)
    
    # URLs do Slack
    print("\n💬 URLs das threads do Slack (uma por linha, linha vazia para terminar):")
    slack_urls = []
    while True:
        url = input("   URL: ").strip()
        if not url:
            break
        slack_urls.append(url)
    
    # Contexto adicional
    print("\n📝 Contexto adicional (linha vazia para terminar):")
    context_lines = []
    while True:
        line = input("   ").strip()
        if not line:
            break
        context_lines.append(line)
    additional_context = "\n".join(context_lines) if context_lines else None
    
    # Usar IA?
    use_ai = input("\n🤖 Usar IA para análise? (S/n): ").strip().lower() != 'n'
    
    # Gera o postmortem
    print("\n" + "-"*60)
    
    generator = PostmortemGenerator(config)
    postmortem = generator.generate(
        title=title,
        incident_issue_url=incident_url,
        jira_urls=jira_urls,
        slack_urls=slack_urls,
        customer_impact=customer_impact,
        start_time=start_time,
        end_time=end_time,
        additional_context=additional_context,
        use_ai=use_ai
    )
    
    # Formata e salva
    formatter = get_formatter(config.output)
    filepath = formatter.save(postmortem)
    
    print(f"\n📄 Postmortem salvo em: {filepath}")
    
    # Preview
    preview = input("\n👀 Mostrar preview? (s/N): ").strip().lower()
    if preview == 's':
        print("\n" + "="*60)
        print(formatter.format(postmortem))
        print("="*60)


def cli_mode(args: argparse.Namespace, config: AppConfig) -> None:
    """
    Modo CLI com argumentos.
    
    Args:
        args: Argumentos da linha de comando.
        config: Configurações da aplicação.
    """
    # Valida argumentos obrigatórios
    if not args.title:
        print("❌ Título é obrigatório! Use --title")
        sys.exit(1)
    
    # Parse das URLs
    jira_urls = args.jira or []
    slack_urls = args.slack or []
    
    # Parse das datas
    start_time = parse_datetime(args.start) if args.start else None
    end_time = parse_datetime(args.end) if args.end else None
    
    # Gera o postmortem
    generator = PostmortemGenerator(config)
    postmortem = generator.generate(
        title=args.title,
        incident_issue_url=args.incident_url or "",
        jira_urls=jira_urls,
        slack_urls=slack_urls,
        customer_impact=args.impact or "A ser determinado",
        start_time=start_time,
        end_time=end_time,
        additional_context=args.context,
        use_ai=not args.no_ai
    )
    
    # Formata e salva
    formatter = get_formatter(config.output)
    
    if args.output:
        filepath = formatter.save(postmortem, args.output)
    else:
        filepath = formatter.save(postmortem)
    
    print(f"\n📄 Postmortem salvo em: {filepath}")
    
    # Cria no Notion se solicitado (e não for modo only-local)
    if args.notion and not args.only_local:
        if not config.notion.is_valid():
            print("⚠️  Configuração do Notion incompleta. Verifique NOTION_API_TOKEN.")
        else:
            notion_client = NotionClient(config.notion)
            try:
                result = notion_client.create_page(
                    postmortem,
                    database_id=args.notion_db or config.notion.database_id,
                    parent_page_id=args.notion_parent
                )
                print(f"✅ Página criada no Notion: {result.get('url', 'N/A')}")
            except Exception as e:
                print(f"❌ Erro ao criar página no Notion: {e}")


def main():
    """Função principal."""
    parser = argparse.ArgumentParser(
        description="Postmortem Maker - Automatize a criação de postmortems",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:

  # Modo interativo
  python -m src.main --interactive

  # Modo CLI (salva localmente por padrão)
  python -m src.main --title "Incidente X" --jira URL1 --jira URL2 --slack URL3 --impact "Serviço indisponível"

  # Modo apenas local (salva em ./output como .md, não envia para Notion)
  python -m src.main --title "Incidente X" --jira URL1 --only-local

  # Salvar no Notion
  python -m src.main --title "Incidente X" --jira URL1 --notion --notion-db DATABASE_ID
        """
    )
    
    # Argumentos gerais
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Executa em modo interativo"
    )
    
    parser.add_argument(
        "-t", "--title",
        help="Título do postmortem"
    )
    
    parser.add_argument(
        "--incident-url",
        help="URL da issue principal de intercorrência"
    )
    
    parser.add_argument(
        "--impact",
        help="Descrição do impacto no cliente"
    )
    
    # Datas
    parser.add_argument(
        "--start",
        help="Data/hora inicial (DD/MM/YYYY HH:MM)"
    )
    
    parser.add_argument(
        "--end",
        help="Data/hora final (DD/MM/YYYY HH:MM)"
    )
    
    # URLs de fontes
    parser.add_argument(
        "-j", "--jira",
        action="append",
        help="URL de issue do Jira (pode ser usado múltiplas vezes)"
    )
    
    parser.add_argument(
        "-s", "--slack",
        action="append",
        help="URL de thread do Slack (pode ser usado múltiplas vezes)"
    )
    
    # Contexto adicional
    parser.add_argument(
        "-c", "--context",
        help="Contexto adicional para análise"
    )
    
    # IA
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Desabilita análise com IA"
    )
    
    # Output
    parser.add_argument(
        "-o", "--output",
        help="Nome do arquivo de saída"
    )
    
    # Output mode
    parser.add_argument(
        "--only-local",
        action="store_true",
        help="Salva apenas localmente como arquivo .md (não envia para Notion)"
    )

    # Notion
    parser.add_argument(
        "--notion",
        action="store_true",
        help="Cria página no Notion"
    )

    parser.add_argument(
        "--notion-db",
        help="ID do database do Notion"
    )

    parser.add_argument(
        "--notion-parent",
        help="ID da página pai no Notion"
    )

    args = parser.parse_args()
    
    # --only-local and --notion are mutually exclusive
    if args.only_local and args.notion:
        print("⚠️  As opções --only-local e --notion são mutuamente exclusivas.")
        print("   Use --only-local para salvar apenas localmente ou --notion para enviar ao Notion.")
        sys.exit(1)
    
    # Carrega configurações
    config = get_config()
    
    # Valida configurações críticas
    errors = config.validate()
    if errors:
        print("\n⚠️  Avisos de configuração:")
        for error in errors:
            print(f"   - {error}")
        print("\nConfigure as variáveis de ambiente ou crie um arquivo .env")
        print("Veja .env.example para referência.\n")
    
    # Executa
    if args.interactive:
        interactive_mode(config)
    elif args.title or args.jira or args.slack:
        cli_mode(args, config)
    else:
        parser.print_help()
        print("\n💡 Use --interactive para modo interativo ou forneça --title")


if __name__ == "__main__":
    main()
