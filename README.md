# 🔧 Postmortem Maker

> **PostMortems make devs sad, use this instead.** 😎

Automatize a criação de postmortems coletando informações do Jira e Slack, com análise assistida por IA. Via CLI ou interface Web.

![Postmortem Maker - Interface Web](docs/images/screenshot.png)

## 📋 Sobre

O Postmortem Maker é uma ferramenta desenvolvida para **eliminar a dor** de criar documentos de postmortem. Ele:

- 📋 Busca automaticamente informações de issues do **Jira**
- 💬 Coleta discussões de threads do **Slack**
- 🤖 Utiliza **IA (OpenAI)** para análise de causa raiz e sugestões de melhoria
- 📄 Gera documentos formatados em **Markdown** compatível com **Notion**
- 🇧🇷 Saída em **Português Brasileiro**

## 🚀 Instalação

### 1. Clone o repositório

```bash
cd /path/to/projects
git clone <repo-url> postmortem-maker
cd postmortem-maker
```

### 2. Crie um ambiente virtual

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Configure as variáveis de ambiente

```bash
cp .env.example .env
# Edite o arquivo .env com suas credenciais
```

## ⚙️ Configuração

### Jira

1. Acesse seu perfil Atlassian: https://id.atlassian.com/manage-profile/security/api-tokens
2. Crie um novo API Token
3. Configure no `.env`:

```env
JIRA_BASE_URL=https://sua-empresa.atlassian.net
JIRA_EMAIL=seu-email@empresa.com
JIRA_API_TOKEN=seu-token-api
```

### Slack

1. Crie um Slack App em https://api.slack.com/apps
2. Vá em **OAuth & Permissions** na sidebar
3. Adicione os scopes necessários:

   **Para User Token (recomendado):** Em "User Token Scopes", adicione:
   - `channels:history` - ler mensagens em canais públicos
   - `channels:read` - ver informações de canais
   - `groups:history` - ler mensagens em canais privados
   - `groups:read` - ver informações de canais privados
   - `users:read` - ver perfis de usuários

   **Para Bot Token (alternativa):** Em "Bot Token Scopes", adicione os mesmos scopes acima.

4. Clique em **Install to Workspace** (ou **Reinstall** se já instalado)
5. Copie o token apropriado:
   - **User OAuth Token** (começa com `xoxp-`) - age em seu nome, acessa canais que você participa
   - **Bot User OAuth Token** (começa com `xoxb-`) - precisa ser convidado para os canais

6. Configure no `.env`:

```env
SLACK_BOT_TOKEN=xoxb-seu-bot-token      # Opcional se usar user token
SLACK_USER_TOKEN=xoxp-seu-user-token    # Recomendado
```

> **Nota:** O User Token é recomendado pois acessa automaticamente todos os canais que você participa. O Bot Token requer que o bot seja convidado para cada canal.

### OpenAI (Opcional)

Para análise assistida por IA:

1. Obtenha uma API key em https://platform.openai.com/api-keys
2. Configure no `.env`:

```env
OPENAI_API_KEY=sk-sua-api-key
OPENAI_MODEL=gpt-4o  # ou gpt-4-turbo, gpt-3.5-turbo
```

### LLM Customizado (Alternativa ao OpenAI)

Se você possui um LLM local (como LM Studio, Ollama, ou outro servidor compatível) ou deseja usar um endpoint de LLM externo, pode usá-lo em vez da OpenAI:

**Via CLI:**
```bash
python -m src.main --title "Incidente X" --jira URL1 --llm-endpoint http://192.168.15.6:1234/api/v1/chat
```

**Via Interface Web:** Marque a opção "Usar LLM customizado" e informe a URL do endpoint.

**Via variáveis de ambiente (opcional):**
```env
LOCAL_LLM_URL=http://192.168.15.6:1234/api/v1/chat
LOCAL_LLM_MODEL=liquid/lfm2.5-1.2b
```

> **Nota:** O LLM deve expor uma API compatível com o formato `{"model": "...", "system_prompt": "...", "input": "..."}`.

### Notion (Opcional)

Para criar páginas diretamente no Notion:

1. Crie uma integração em https://www.notion.so/my-integrations
2. Compartilhe a página/database com a integração
3. Configure no `.env`:

```env
NOTION_API_TOKEN=secret_seu-token
NOTION_DATABASE_ID=id-do-database
```

## 📖 Uso

### Interface Web (Streamlit)

A forma mais fácil e visual de usar:

```bash
streamlit run app.py
```

Abre automaticamente no navegador em `http://localhost:8501`.

**Funcionalidades:**
- Interface limpa e intuitiva
- Preview em tempo real do Markdown gerado
- Download do arquivo `.md`
- Exportação direta para Notion

### Modo Interativo (CLI)

O modo mais fácil de usar:

```bash
python -m src.main --interactive
```

Você será guiado para informar:
- Título do postmortem
- URL da issue de intercorrência
- Impacto no cliente
- Datas de início e fim
- URLs de issues do Jira
- URLs de threads do Slack
- Contexto adicional

### Modo CLI

Para automação ou scripts:

```bash
python -m src.main \
  --title "Incidente - Serviço X indisponível" \
  --incident-url "https://empresa.atlassian.net/browse/INC-123" \
  --impact "Serviço totalmente indisponível para clientes" \
  --start "18/02/2026 21:25" \
  --end "19/02/2026 13:54" \
  --jira "https://empresa.atlassian.net/browse/PROJ-456" \
  --jira "https://empresa.atlassian.net/browse/PROJ-789" \
  --slack "https://empresa.slack.com/archives/C01234567/p1234567890123456" \
  --context "Deploy da versão 2.3.0 foi realizado às 21:00"
```

**Usando LLM customizado:**

```bash
python -m src.main \
  --title "Incidente - Serviço X indisponível" \
  --jira "https://empresa.atlassian.net/browse/PROJ-456" \
  --impact "Serviço indisponível" \
  --llm-endpoint http://192.168.15.6:1234/api/v1/chat
```

### Opções Disponíveis

| Opção | Descrição |
|-------|-----------|
| `-i, --interactive` | Modo interativo |
| `-t, --title` | Título do postmortem |
| `--incident-url` | URL da issue principal |
| `--impact` | Impacto no cliente |
| `--start` | Data/hora inicial (DD/MM/YYYY HH:MM) |
| `--end` | Data/hora final (DD/MM/YYYY HH:MM) |
| `-j, --jira` | URL de issue do Jira (múltiplo) |
| `-s, --slack` | URL de thread do Slack (múltiplo) |
| `-c, --context` | Contexto adicional |
| `--no-ai` | Desabilita análise com IA |
| `--llm-endpoint URL` | Usa LLM customizado (local ou externo) em vez da OpenAI (informe a URL do endpoint) |
| `-o, --output` | Nome do arquivo de saída |
| `--only-local` | Salva apenas localmente (não envia para Notion) |
| `--notion` | Cria página no Notion |
| `--notion-db` | ID do database do Notion |

## 📄 Formato de Saída

O postmortem gerado segue este formato:

```markdown
# INTERCORRÊNCIA - Título do Incidente

[Link para a issue de Intercorrência](URL)

**Data e Hora Inicial:** DD/MM/YYYY HH:MM BRT
**Data e Hora Final:** DD/MM/YYYY HH:MM BRT
**Duração:** XhYYmin
**Impacto no cliente: Descrição do impacto**

## **Linha do Tempo da Intercorrência**

| Data e Hora | Ator (Quem) | Evento |
| --- | --- | --- |
| DD/MM/YYYY HH:MM | Pessoa | Descrição do evento |

## **Causa Raíz**

Descrição detalhada da causa raiz...

**Pontos importantes:**
- Ponto 1
- Ponto 2

## **Processo de Resolução**

Como o problema foi resolvido...

## **Oportunidades de Melhoria**

**Sugestão de melhoria 1:** Descrição...

## **Plano de Ação**

| Ação | Responsável | Issue(s) |
| --- | --- | --- |
| Ação a ser tomada | Responsável | PROJ-XXX |
```

## 🏗️ Arquitetura

```
postmortem-maker/
├── src/
│   ├── __init__.py
│   ├── main.py              # CLI e ponto de entrada
│   ├── config.py            # Gerenciamento de configuração
│   ├── models.py            # Modelos de dados
│   ├── jira_client.py       # Cliente da API do Jira
│   ├── slack_client.py      # Cliente da API do Slack
│   ├── notion_client.py     # Cliente da API do Notion
│   ├── ai_analyzer.py       # Análise com OpenAI
│   ├── postmortem_generator.py  # Orquestrador principal
│   └── output_formatter.py  # Formatação Markdown/Notion
├── output/                  # Arquivos gerados
├── requirements.txt
├── .env.example
└── README.md
```

## 🧪 Desenvolvimento

### Testes

```bash
pytest tests/ -v --cov=src
```

### Formatação

```bash
black src/
isort src/
```

### Type checking

```bash
mypy src/
```

## 🤝 Contribuindo

1. Fork o repositório
2. Crie uma branch para sua feature (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -am 'Adiciona nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Crie um Pull Request

## 📝 Licença

MIT License - veja o arquivo LICENSE para detalhes.

## 🙏 Agradecimentos

Desenvolvido para tornar os postmortems menos dolorosos e mais produtivos.
