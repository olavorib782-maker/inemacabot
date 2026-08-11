# plano_implementacao.md

# Plano de Implementação do InemacaBot

## 1. Objetivo deste documento

Este documento acompanha a execução prática do projeto.

Diferentemente do `PLANO.md`, que apresenta a visão geral e a direção do projeto, este arquivo registra o que já foi implementado, o que precisa ser concluído e a ordem recomendada para as próximas etapas.

---

## 2. Estado da implementação

### Concluído

- [x] Estrutura inicial do bot em Python.
- [x] Integração com `python-telegram-bot`.
- [x] Autorização por `TELEGRAM_ALLOWED_USER_ID`.
- [x] Comando `/start`.
- [x] Comando `/ajuda`.
- [x] Comando `/limpar`.
- [x] Recebimento de mensagens de texto.
- [x] Cliente assíncrono para API compatível com OpenAI.
- [x] Tratamento de timeout e erros do cliente de IA.
- [x] Validação das variáveis de ambiente.
- [x] Histórico de conversa em memória.
- [x] Limite configurável do histórico.
- [x] `asyncio.Lock` para proteger o processamento do histórico.
- [x] Divisão de respostas maiores que 4096 caracteres.
- [x] `.env.example`.
- [x] `.gitignore` protegendo `.env`.
- [x] `README.md`.
- [x] `requirements.txt` com versões fixadas.
- [x] `requirements-dev.txt`.
- [x] `pytest.ini`.
- [x] Testes iniciais do histórico.
- [x] Testes iniciais do cliente de IA.
- [x] Testes iniciais de configuração.
- [x] Testes iniciais de autorização e divisão de mensagens.

---

## 3. Pendências imediatas

### 3.1 Instalar dependências

No ambiente local:

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

Depois verificar:

```bash
python -m pip show python-telegram-bot
python -m pip show openai
python -m pip show python-dotenv
python -m pip show pytest
python -m pip show pytest-asyncio
```

---

### 3.2 Criar configuração local

Criar uma cópia do `.env.example`:

Windows CMD:

```bat
copy .env.example .env
```

Preencher o `.env` com os valores reais.

Nunca enviar o `.env` para o GitHub.

---

### 3.3 Executar testes

Executar:

```bash
pytest
```

O objetivo é que toda a suíte passe sem erros.

Também manter a verificação de compilação:

```bash
python -m py_compile bot.py ai_client.py config.py conversation_history.py
```

---

## 4. Organização dos testes

Os arquivos de teste atualmente fornecidos estão na raiz do projeto:

- `test_bot.py`;
- `test_config.py`;
- `test_ai_client.py`;
- `test_conversation_history.py`.

A estrutura recomendada é:

```text
inemacabot/
├── bot.py
├── ai_client.py
├── config.py
├── conversation_history.py
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
├── README.md
├── PLANO.md
├── plano_implementacao.md
├── .env.example
├── .gitignore
└── tests/
    ├── test_bot.py
    ├── test_config.py
    ├── test_ai_client.py
    └── test_conversation_history.py
```

### Tarefa

- [ ] Criar `tests/`.
- [ ] Mover os quatro arquivos de teste para `tests/`.
- [ ] Executar `pytest` novamente.
- [ ] Confirmar que todos os testes continuam sendo encontrados.

---

## 5. Validação funcional do bot

Depois da instalação e configuração:

1. iniciar o bot;
2. enviar `/start` pelo usuário autorizado;
3. testar uma mensagem simples;
4. enviar uma segunda mensagem verificando o uso do contexto;
5. executar `/ajuda`;
6. executar `/limpar`;
7. verificar que o contexto foi apagado;
8. testar uma resposta muito longa;
9. testar uma falha de configuração;
10. testar um usuário não autorizado.

---

## 6. Critérios de aceite da primeira versão

A primeira versão poderá ser considerada estabilizada quando:

- [ ] o projeto instalar sem erros;
- [ ] o `.env` for carregado corretamente;
- [ ] o usuário autorizado conseguir conversar com o bot;
- [ ] usuários não autorizados não forem processados;
- [ ] o histórico funcionar dentro do limite configurado;
- [ ] `/limpar` apagar o histórico;
- [ ] respostas maiores que 4096 caracteres forem divididas;
- [ ] falhas da API não expuserem detalhes sensíveis;
- [ ] todos os testes automatizados passarem;
- [ ] `py_compile` passar sem erros;
- [ ] Git estiver limpo antes do commit;
- [ ] documentação refletir o estado real do projeto.

---

## 7. Próxima etapa: filas

Depois da estabilização da primeira versão, a próxima grande etapa será trabalhar nas filas.

Objetivo inicial:

- receber uma tarefa;
- colocá-la em uma fila;
- processar a tarefa de forma controlada;
- informar o usuário sobre o andamento;
- evitar que tarefas demoradas bloqueiem desnecessariamente o fluxo do bot.

Essa etapa deve ser implementada depois da conclusão dos critérios de aceite da primeira versão.

---

## 8. Evolução posterior

Após as filas, o projeto poderá avançar gradualmente para uma arquitetura de agente.

Possíveis etapas:

1. definição de tarefas;
2. ferramentas;
3. memória persistente;
4. múltiplos usuários;
5. banco de dados;
6. observabilidade;
7. integração com serviços externos;
8. voz e multimídia;
9. automações mais complexas.

Essas funcionalidades não fazem parte da estabilização da primeira versão.

---

## 9. Estratégia de Git

Cada etapa deve ser registrada em commits pequenos e claros.

Exemplos:

```text
Prepara configuração do projeto
Documenta instalação e execução
Adiciona testes iniciais
Implementa divisão de mensagens longas
Organiza suíte de testes
Prepara estrutura de filas
```

Antes de cada commit:

```bash
git status
pytest
python -m py_compile bot.py ai_client.py config.py conversation_history.py
```

Depois:

```bash
git add .
git commit -m "Descrição objetiva da alteração"
git push origin main
```

---

## 10. Regra de evolução

Não avançar para uma nova camada enquanto a anterior estiver quebrada.

A ordem de trabalho será:

```text
Fundação
   ↓
Testes
   ↓
Documentação
   ↓
Estabilização
   ↓
Filas
   ↓
Agente
   ↓
Ferramentas e memória
   ↓
Recursos avançados
```

O objetivo é evitar crescimento prematuro da complexidade e manter cada etapa verificável.
