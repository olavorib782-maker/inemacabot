# Plano de implementação — Assistente para Telegram

Este plano foi elaborado a partir dos requisitos descritos em
[`prompt_bot_telegram.md`](prompt_bot_telegram.md).

## Situação atual

O projeto contém apenas o documento de requisitos. A implementação do bot ainda
não foi iniciada.

## Decisões técnicas

- Usar Python 3.11 ou superior.
- Usar `python-telegram-bot` para integração com a API oficial do Telegram.
- Usar o SDK `openai` configurado com `base_url`, permitindo provedores
  compatíveis com a API OpenAI.
- Usar `python-dotenv` para carregar as variáveis do arquivo `.env`.
- Receber mensagens por long polling, por ser a alternativa mais simples para
  execução local e em VPS.
- Manter um histórico limitado em memória.
- Usar uma trava assíncrona para preservar a ordem das mensagens e do histórico.
- Dividir respostas em blocos menores que o limite de 4.096 caracteres do
  Telegram.
- Processar somente mensagens de texto.

## Estrutura proposta

```text
inemacabot/
├── bot.py
├── ai_client.py
├── config.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── tests/
│   ├── test_authorization.py
│   ├── test_history.py
│   └── test_message_split.py
└── doc/
    ├── prompt_bot_telegram.md
    └── plano_implementacao.md
```

## Etapas de implementação

### 1. Criar e validar a configuração

Criar `config.py` para carregar e validar as seguintes variáveis:

- `TELEGRAM_BOT_TOKEN`;
- `TELEGRAM_ALLOWED_USER_ID`;
- `AI_API_KEY`;
- `AI_BASE_URL`;
- `AI_MODEL`;
- `AI_SYSTEM_PROMPT`, variável adicional para tornar a instrução configurável;
- `HISTORY_MAX_MESSAGES`, variável opcional com um valor padrão.

O programa deverá encerrar com uma mensagem clara quando uma configuração
obrigatória estiver ausente ou inválida.

### 2. Implementar o cliente de inteligência artificial

Criar `ai_client.py` com as seguintes responsabilidades:

- inicializar o cliente compatível com OpenAI;
- enviar a instrução de sistema, o histórico e a mensagem atual;
- definir um timeout para evitar espera infinita;
- validar respostas vazias ou inválidas;
- tratar erros sem revelar chaves, tokens ou outros dados sensíveis.

### 3. Implementar o histórico da conversa

O histórico será armazenado em memória e deverá:

- manter somente os últimos pares de mensagens;
- adicionar a mensagem e a resposta ao histórico apenas depois de uma chamada
  bem-sucedida;
- ser completamente apagado pelo comando `/limpar`;
- ser reiniciado quando o processo do bot for reiniciado.

Persistência em banco de dados ou arquivo não será adicionada, pois está fora do
escopo do documento.

### 4. Implementar o bot do Telegram

Criar `bot.py` com handlers para:

- `/start`;
- `/limpar`;
- `/ajuda`;
- mensagens de texto;
- erros não tratados.

Antes de processar um comando ou chamar a API de IA, cada handler deverá
comparar o ID do remetente com `TELEGRAM_ALLOWED_USER_ID`. Usuários não
autorizados serão silenciosamente ignorados.

### 5. Implementar o fluxo das mensagens

O processamento seguirá este fluxo:

```text
Validar usuário
    → validar texto
    → carregar histórico
    → chamar API da IA
    → atualizar histórico
    → dividir resposta
    → enviar blocos ao Telegram
```

As mensagens serão processadas de forma serializada para impedir que respostas
simultâneas deixem o histórico fora de ordem.

### 6. Dividir respostas longas

Criar uma função isolada e testável que:

- use uma margem segura, como 4.000 caracteres por mensagem;
- tente dividir primeiro por parágrafos ou quebras de linha;
- faça uma divisão rígida somente quando um trecho individual for muito grande;
- nunca produza blocos vazios;
- preserve todo o conteúdo e sua ordem.

### 7. Aplicar segurança e tratamento de falhas

- Nunca registrar chaves ou tokens no terminal.
- Incluir `.env` no `.gitignore`.
- Registrar erros técnicos no terminal usando `logging`.
- Enviar ao usuário autorizado uma mensagem curta quando a IA estiver
  indisponível.
- Não adicionar automações, ferramentas, agentes ou comandos além dos três
  especificados.

### 8. Criar a documentação

O `README.md` deverá explicar:

1. como criar o bot pelo BotFather;
2. como descobrir o ID do usuário do Telegram;
3. como criar e preencher o arquivo `.env`;
4. como criar o ambiente virtual e instalar as dependências;
5. como iniciar o bot;
6. como testar a autorização e a integração;
7. como manter o processo funcionando em uma VPS usando `systemd`;
8. como diagnosticar os erros mais comuns.

### 9. Criar testes e revisar o projeto

Criar testes para verificar:

- autorização do usuário;
- descarte de usuários desconhecidos antes da chamada à IA;
- limite e limpeza do histórico;
- divisão de mensagens longas;
- configuração ausente ou inválida;
- resposta vazia ou falha da API.

Ao final:

- executar todos os testes;
- verificar a sintaxe e a importação dos arquivos Python;
- revisar o projeto em busca de segredos;
- conferir os comandos documentados em um ambiente limpo.

## Critérios de aceite

A implementação será considerada concluída quando:

- o usuário autorizado conseguir conversar com a IA pelo Telegram;
- usuários desconhecidos não conseguirem consumir a API de IA;
- os comandos `/start`, `/limpar` e `/ajuda` funcionarem;
- o contexto recente da conversa for preservado;
- respostas longas forem enviadas integralmente e na ordem correta;
- configurações e segredos estiverem somente nas variáveis de ambiente;
- falhas forem registradas sem derrubar o processo do bot;
- o README permitir instalar e executar o projeto do zero.

