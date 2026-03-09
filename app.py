"""
Streamlit interface for Postmortem Maker.
A clean, simple web UI to generate postmortems.
"""

import streamlit as st
from datetime import datetime
from typing import Optional

from src.config import get_config
from src.postmortem_generator import PostmortemGenerator
from src.output_formatter import get_formatter, MarkdownFormatter
from src.notion_client import NotionClient


def parse_datetime(date_str: str) -> Optional[datetime]:
    """Parse datetime string in multiple formats."""
    if not date_str or not date_str.strip():
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
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    
    return None


def main():
    # Page config
    st.set_page_config(
        page_title="Postmortem Maker",
        page_icon="🔧",
        layout="centered"
    )
    
    # Header
    st.title("🔧 Postmortem Maker")
    st.markdown("> **Postmortems make devs sad—use this instead.**")
    st.divider()
    
    # Load config
    config = get_config()
    
    # Sidebar - API Status
    with st.sidebar:
        st.header("⚙️ Configuração")
        
        st.subheader("Status das APIs")
        
        # Jira status
        if config.jira.is_valid():
            st.success("✅ Jira configurado")
        else:
            st.warning("⚠️ Jira não configurado")
        
        # Slack status
        if config.slack.is_valid():
            st.success("✅ Slack configurado")
        else:
            st.warning("⚠️ Slack não configurado")
        
        # OpenAI status
        if config.openai.is_valid():
            st.success("✅ OpenAI configurado")
        else:
            st.info("ℹ️ OpenAI não configurado (análise manual)")
        
        # Notion status
        if config.notion.is_valid():
            st.success("✅ Notion configurado")
        else:
            st.info("ℹ️ Notion não configurado")
        
        st.divider()
        st.caption("Configure as APIs no arquivo `.env`")
    
    # Main form
    st.subheader("📋 Informações Básicas")
    
    col1, col2 = st.columns(2)
    
    with col1:
        title = st.text_input(
            "Título da Intercorrência *",
            placeholder="Ex: Serviço X indisponível por timeout"
        )
    
    with col2:
        incident_url = st.text_input(
            "URL da Issue Principal",
            placeholder="https://empresa.atlassian.net/browse/INC-123"
        )
    
    impact = st.text_area(
        "Impacto no Cliente *",
        placeholder="Descreva como o cliente foi afetado...",
        height=80
    )
    
    # Data sources
    st.subheader("📊 Fontes de Dados")
    
    col1, col2 = st.columns(2)
    
    with col1:
        jira_input = st.text_area(
            "Issues do Jira",
            placeholder="Uma por linha:\nPROJ-123\nPROJ-456\nou URLs completas",
            height=120,
            help="Insira chaves (PROJ-123) ou URLs completas do Jira"
        )
    
    with col2:
        slack_input = st.text_area(
            "Threads do Slack",
            placeholder="Uma URL por linha:\nhttps://empresa.slack.com/archives/...",
            height=120,
            help="URLs de threads do Slack"
        )
    
    # Advanced options
    with st.expander("⚙️ Opções Avançadas"):
        col1, col2 = st.columns(2)
        
        with col1:
            start_date = st.text_input(
                "Data/Hora Inicial",
                placeholder="DD/MM/YYYY HH:MM (opcional)",
                help="Deixe em branco para detectar automaticamente"
            )
        
        with col2:
            end_date = st.text_input(
                "Data/Hora Final",
                placeholder="DD/MM/YYYY HH:MM (opcional)",
                help="Deixe em branco para detectar automaticamente"
            )
        
        context = st.text_area(
            "Contexto Adicional",
            placeholder="Informações extras para a análise (deploys, mudanças recentes, etc.)",
            height=80
        )
    
    # Options
    st.subheader("🎛️ Opções")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        use_ai = st.checkbox(
            "Usar análise com IA",
            value=config.openai.is_valid(),
            disabled=not config.openai.is_valid(),
            help="Requer OpenAI API configurada"
        )
    
    with col2:
        use_local_llm = st.checkbox(
            "Usar LLM customizado",
            value=False,
            help="Usa um LLM customizado (local ou endpoint externo) em vez da OpenAI"
        )
    
    with col3:
        export_notion = st.checkbox(
            "Exportar para Notion",
            value=False,
            disabled=not config.notion.is_valid(),
            help="Requer Notion API configurada"
        )
    
    # Custom LLM URL input
    local_llm_url = None
    if use_local_llm:
        local_llm_url = st.text_input(
            "URL do LLM Customizado",
            value=config.local_llm.base_url,
            placeholder="http://192.168.15.6:1234/api/v1/chat",
            help="Endpoint da API do LLM (local ou externo)"
        )
    
    if export_notion:
        notion_db = st.text_input(
            "ID do Database do Notion",
            value=config.notion.database_id or "",
            help="ID do database onde o postmortem será criado"
        )
    
    st.divider()
    
    # Generate button
    generate_clicked = st.button(
        "🚀 Gerar Postmortem",
        type="primary",
        use_container_width=True
    )
    
    # Process and generate
    if generate_clicked:
        # Validation
        if not title:
            st.error("❌ Título é obrigatório!")
            return
        
        if not impact:
            st.error("❌ Impacto no cliente é obrigatório!")
            return
        
        # Parse inputs
        jira_urls = [line.strip() for line in jira_input.split("\n") if line.strip()]
        slack_urls = [line.strip() for line in slack_input.split("\n") if line.strip()]
        
        if not jira_urls and not slack_urls:
            st.warning("⚠️ Nenhuma fonte de dados informada. O postmortem será gerado apenas com as informações básicas.")
        
        # Parse dates
        start_time = parse_datetime(start_date) if start_date else None
        end_time = parse_datetime(end_date) if end_date else None
        
        # Generate postmortem
        with st.spinner("🔄 Gerando postmortem..."):
            try:
                # Configure local LLM if specified
                if use_local_llm and local_llm_url:
                    config.local_llm.base_url = local_llm_url
                
                generator = PostmortemGenerator(config, use_local_llm=use_local_llm)
                
                postmortem = generator.generate(
                    title=title,
                    incident_issue_url=incident_url or "",
                    jira_urls=jira_urls,
                    slack_urls=slack_urls,
                    customer_impact=impact,
                    start_time=start_time,
                    end_time=end_time,
                    additional_context=context if context else None,
                    use_ai=use_ai or use_local_llm
                )
                
                # Format output
                formatter = MarkdownFormatter(config.output)
                markdown_content = formatter.format(postmortem)
                
                # Store in session state
                st.session_state['postmortem'] = postmortem
                st.session_state['markdown'] = markdown_content
                
                st.success("✅ Postmortem gerado com sucesso!")
                
                # Export to Notion if requested
                if export_notion and config.notion.is_valid():
                    try:
                        notion_client = NotionClient(config.notion)
                        database_id = notion_db if notion_db else config.notion.database_id
                        if database_id:
                            page_url = notion_client.create_postmortem_page(
                                postmortem, database_id
                            )
                            st.success(f"📝 Página criada no Notion: {page_url}")
                    except Exception as e:
                        st.error(f"❌ Erro ao criar página no Notion: {e}")
                
            except Exception as e:
                st.error(f"❌ Erro ao gerar postmortem: {e}")
                return
    
    # Display result
    if 'markdown' in st.session_state:
        st.divider()
        st.subheader("📄 Postmortem Gerado")
        
        # Tabs for preview
        tab1, tab2 = st.tabs(["📝 Preview", "📋 Markdown"])
        
        with tab1:
            st.markdown(st.session_state['markdown'])
        
        with tab2:
            st.code(st.session_state['markdown'], language="markdown")
        
        # Download button
        filename = f"postmortem_{title.replace(' ', '_')[:30]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        
        st.download_button(
            label="⬇️ Download Postmortem",
            data=st.session_state['markdown'],
            file_name=filename,
            mime="text/markdown",
            use_container_width=True
        )


if __name__ == "__main__":
    main()
