# InemacaBot

Bot para Telegram com integração de Inteligência Artificial.

## Recursos

- Integração com Telegram
- Integração com OpenRouter
- Histórico de conversas
- Controle de usuários autorizados
- Configuração por arquivo `.env`
- Arquitetura preparada para expansão

## Tecnologias

- Python 3
- python-telegram-bot
- OpenRouter API
- python-dotenv

## Estrutura

```
inemacabot/
│
├── bot.py
├── ai_client.py
├── config.py
├── conversation_history.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Instalação

Clone o projeto:

```bash
git clone https://github.com/olavorib782-maker/inemacabot.git
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

Crie um arquivo `.env` usando como modelo o `.env.example`.

Execute:

```bash
python bot.py
```

## Configuração

Exemplo:

```env
TELEGRAM_BOT_TOKEN=SEU_TOKEN
TELEGRAM_ALLOWED_USER_ID=SEU_ID
AI_BASE_URL=https://openrouter.ai/api/v1
AI_MODEL=openrouter/free
OPENROUTER_API_KEY=SUA_CHAVE
AI_SYSTEM_PROMPT=Seu prompt
HISTORY_MAX_MESSAGES=20
```

## Licença

MIT License