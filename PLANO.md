# Plano de execução — INEMACABOT

1. Criar o projeto Node.js com TypeScript e configurar as variáveis do Telegram e OpenAI.
2. Conectar o bot ao Telegram para receber mensagens de texto.
3. Enviar cada mensagem à IA, que deve retornar apenas uma decisão em JSON: responder, perguntar ou executar uma skill.
4. Validar a decisão:
   - `respond`: enviar a resposta;
   - `ask`: pedir a informação faltante;
   - `skill`: conferir campos obrigatórios e retornar uma execução simulada.
5. Testar os três cenários e documentar como instalar, configurar e iniciar.

## Objetivo da primeira versão

Comprovar que o bot recebe uma mensagem, interpreta o pedido e devolve a ação correta — sem banco de dados ou integrações reais.
