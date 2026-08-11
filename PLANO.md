# PLANO.md

# InemacaBot - Plano do Projeto

## 1. Visão geral

O InemacaBot é um bot de Telegram desenvolvido em Python que recebe mensagens de um usuário autorizado e utiliza um provedor de IA compatível com a API da OpenAI para gerar respostas.

A primeira versão funcional já possui o núcleo operacional do bot, incluindo autorização, configuração por variáveis de ambiente, cliente assíncrono de IA, histórico de conversa em memória e tratamento básico de erros.

Este documento descreve o estado atual e a direção planejada do projeto.

---

## 2. Objetivos

### Objetivo principal

Construir um bot de Telegram simples, seguro e organizado, que sirva como base para futuras evoluções em direção a um agente mais completo.

### Objetivos da primeira fase

- Restringir o acesso a um usuário autorizado.
- Receber mensagens de texto pelo Telegram.
- Enviar o contexto da conversa ao provedor de IA.
- Retornar a resposta ao usuário.
- Manter histórico de conversa em memória.
- Permitir limpar o contexto com `/limpar`.
- Tratar falhas da API sem expor detalhes internos.
- Respeitar o limite de tamanho das mensagens do Telegram.
- Manter configuração e credenciais fora do código-fonte.
- Criar testes automatizados para os componentes principais.
- Documentar instalação, configuração, execução e testes.

---

## 3. Estado atual

A implementação atual está em Python 3.11+ e utiliza:

- `python-telegram-bot` para integração com o Telegram;
- `openai` para comunicação assíncrona com uma API compatível;
- `python-dotenv` para carregamento de variáveis de ambiente;
- `pytest` e `pytest-asyncio` para testes.

O projeto já possui:

- `bot.py`;
- `ai_client.py`;
- `config.py`;
- `conversation_history.py`;
- `.env.example`;
- `.gitignore`;
- `README.md`;
- `requirements.txt`;
- `requirements-dev.txt`;
- `pytest.ini`;
- testes para bot, configuração, cliente de IA e histórico.

O `bot.py` já possui a função `split_message`, que divide respostas acima do limite de 4096 caracteres antes do envio ao Telegram.

As dependências principais estão fixadas em versões no `requirements.txt`.

---

## 4. Arquitetura atual

### `bot.py`

Responsável pelo ponto de entrada da aplicação e pelos handlers do Telegram.

Principais responsabilidades:

- autorização do usuário;
- comandos `/start`, `/ajuda` e `/limpar`;
- recebimento de mensagens de texto;
- chamada do cliente de IA;
- atualização do histórico;
- divisão de respostas longas;
- tratamento de erros.

### `ai_client.py`

Responsável pela comunicação assíncrona com o provedor de IA.

Deve:

- utilizar as configurações fornecidas pelo ambiente;
- enviar o prompt de sistema;
- incluir o histórico da conversa;
- enviar a mensagem atual do usuário;
- aplicar timeout;
- transformar falhas do provedor em erros seguros para o bot.

### `config.py`

Responsável por carregar e validar as configurações do ambiente.

Variáveis principais:

- `TELEGRAM_BOT_TOKEN`;
- `TELEGRAM_ALLOWED_USER_ID`;
- `AI_API_KEY`;
- `AI_BASE_URL`;
- `AI_MODEL`;
- `AI_SYSTEM_PROMPT`;
- `HISTORY_MAX_MESSAGES`.

### `conversation_history.py`

Mantém o histórico em memória.

O histórico trabalha com pares `user`/`assistant`, possui limite configurável e disponibiliza um `asyncio.Lock` para sincronização durante o processamento das mensagens.

### Configuração

As credenciais reais ficam em `.env`, que não deve ser versionado. O `.env.example` documenta as variáveis necessárias.

---

## 5. Testes

A suíte inicial cobre:

- autorização do usuário;
- divisão de mensagens longas;
- histórico e limite de mensagens;
- limpeza do histórico;
- exposição do `asyncio.Lock`;
- carregamento e validação da configuração;
- inclusão do histórico na chamada de IA;
- timeout;
- resposta vazia;
- ausência de escolhas na resposta da IA;
- erros inesperados do cliente de IA.

### Organização planejada

Os testes devem ficar organizados em uma pasta `tests/`, mantendo a estrutura do projeto mais clara e alinhada à documentação.

---

## 6. Segurança e boas práticas

O projeto deve preservar as seguintes regras:

1. Nunca colocar tokens ou chaves reais no código.
2. Nunca versionar `.env`.
3. Não expor detalhes internos de exceções ao usuário.
4. Autorizar o usuário antes de processar comandos ou mensagens.
5. Manter dependências fixadas para reproduzir o ambiente.
6. Evitar registrar informações sensíveis nos logs.
7. Executar testes antes de cada alteração relevante.
8. Manter commits pequenos e descritivos.

---

## 7. Limitações atuais

A versão atual ainda possui algumas limitações:

- o histórico é mantido apenas em memória;
- reiniciar o processo apaga o contexto;
- cada instância atende um único usuário autorizado;
- não existe persistência em banco de dados;
- o bot trabalha essencialmente com mensagens de texto;
- não há ainda uma camada de filas ou processamento de tarefas;
- os testes enviados atualmente estão na raiz do projeto e devem ser reorganizados em `tests/`.

Essas limitações são aceitáveis para a primeira versão e não precisam ser resolvidas todas de uma vez.

---

## 8. Evolução planejada

### Fase 1 - Fundação

- estabilizar instalação;
- validar configuração;
- consolidar testes;
- organizar documentação;
- manter dependências reproduzíveis.

### Fase 2 - Robustez

- organizar a suíte em `tests/`;
- ampliar cobertura de testes;
- melhorar observabilidade e logs;
- revisar tratamento de erros;
- validar comportamento em mensagens extensas.

### Fase 3 - Filas e processamento

Introduzir uma estrutura de filas para permitir que o bot lide melhor com tarefas que possam demorar ou precisar de processamento separado.

Essa fase será desenvolvida somente depois que a fundação estiver estável.

### Fase 4 - Agente

Evoluir o bot de um simples interlocutor para um agente capaz de:

- interpretar objetivos;
- executar etapas;
- utilizar ferramentas;
- manter contexto de forma mais estruturada;
- tratar tarefas de maneira assíncrona.

### Fase 5 - Recursos avançados

Somente depois das fases anteriores poderão ser avaliados:

- memória persistente;
- múltiplos usuários;
- ferramentas externas;
- banco de dados;
- filas distribuídas;
- observabilidade;
- integração com outros serviços;
- recursos de voz e multimídia.

---

## 9. Princípio de desenvolvimento

O projeto será desenvolvido de forma incremental.

A prioridade é:

**funcionar -> testar -> documentar -> estabilizar -> evoluir.**

Novos recursos não devem ser adicionados antes que a base correspondente esteja suficientemente testada.

A intenção é construir uma fundação pequena e confiável para, posteriormente, transformar o InemacaBot em um agente mais completo.
