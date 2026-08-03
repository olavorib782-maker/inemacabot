# INEMACABOT — guia para alterações

## Contexto

Este repositório implementa um bot pessoal do Telegram em Python. Ele permite que
um único usuário autorizado converse com um provedor de IA compatível com a API
OpenAI. A primeira versão usa long polling, não possui banco de dados e não
executa ferramentas, skills ou automações externas.

## Arquitetura e fluxo

```text
Telegram -> bot.py -> validação do usuário -> histórico em memória
         -> ai_client.py -> API compatível com OpenAI -> resposta no Telegram
```

- `bot.py`: ponto de entrada, handlers do Telegram e autorização.
- `config.py`: carrega o `.env` e valida as configurações obrigatórias.
- `ai_client.py`: cliente assíncrono da IA, timeout e tratamento seguro de erros.
- `conversation_history.py`: histórico recente em memória e trava assíncrona.
- `requirements.txt`: dependências de execução.

Os comandos disponíveis são `/start`, `/ajuda` e `/limpar`. Mensagens de usuários
que não correspondem a `TELEGRAM_ALLOWED_USER_ID` devem ser ignoradas antes de
qualquer chamada à IA.

## Configuração

O arquivo `.env` é local e não deve ser exibido, versionado ou incluído em logs.
As variáveis necessárias são:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ALLOWED_USER_ID`
- `AI_API_KEY`
- `AI_BASE_URL`
- `AI_MODEL`
- `AI_SYSTEM_PROMPT`

`HISTORY_MAX_MESSAGES` é opcional e assume o padrão `20`.

## Comandos de desenvolvimento e teste

No PowerShell, com o ambiente virtual local:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m compileall -q .
.\.venv\Scripts\python.exe bot.py
```

Ainda não há suíte de testes automatizados. Ao adicionar comportamento, crie
testes com `unittest` ou `pytest` e execute o comando adequado (por exemplo,
`python -m pytest`) antes de concluir a alteração.

## Regras para futuras alterações

1. Preserve a autorização em todos os handlers, antes de acessar histórico ou IA.
2. Nunca registre, retorne em mensagens de erro ou versione tokens, chaves e o
   conteúdo do `.env`.
3. Mantenha o cliente de IA assíncrono e a trava do histórico durante a leitura,
   chamada à IA e gravação do par de mensagens, para não inverter o contexto.
4. Só adicione o par ao histórico após uma resposta bem-sucedida da IA.
5. Preserve erros curtos e seguros para o usuário; detalhes técnicos devem ficar
   apenas nos logs, sem dados sensíveis.
6. Trate respostas acima do limite do Telegram (4.096 caracteres) dividindo-as
   antes de enviá-las. O código atual ainda não implementa essa divisão.
7. Não introduza persistência, integrações externas, execução de ferramentas ou
   múltiplos usuários sem atualizar a arquitetura, a configuração e a cobertura
   de testes.
8. Mantenha compatibilidade com Python 3.11 ou superior e atualize
   `requirements.txt` quando uma nova dependência for necessária.
