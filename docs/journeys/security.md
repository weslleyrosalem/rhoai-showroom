# Jornada: confiança para agentes operacionais

A Aurora Supply precisa responder sobre estoque e propor reposição sem permitir compras autônomas. O cliente vê uma pergunta atravessar documentos, modelo, ferramentas e políticas, e pode verificar cada decisão.

**Préflight:** marque explicitamente os itens em execução no seu cluster. MCP Gateway/Lifecycle e tracing no Playground são TP; NeMo base é GA; agentes salvos são DP; OpenShell é um addon externo experimental. Não apresente módulos documentados como implantados.

## Versão de20minutos

| Tempo | O que fazer | O que apontar |
|---|---|---|
|0–2|Apresentar Aurora e namespace `ai-showroom`|Dados sintéticos, identidades, escopo de somente leitura|
|2–6|Perguntar sobre estoque e reposição do AS-001|RAG cita políticas; MCP consulta estoque; recomendação mostra versão da previsão e não cria pedido|
|6–9|Abrir trace nova no MLflow/Playground, quando habilitada|Spans reais, chamadas e tempo; não apenas texto gerado|
|9–12|Testar acesso MCP sem token, SA não permitida e SA permitida|401/403/sucesso; VirtualServer organiza descoberta e não substitui auth|
|12–15|Executar checks NeMo permitidos e bloqueados|Regra explícita responsável; CPU, sem chamada LLM nesses checks|
|15–18|Abrir uma execução Garak completa no EvalHub|Configuração, amostras, resultados e limitações|
|18–20|Cliente reformula pergunta ou muda prompt versionado|Test drive repetível, sem alterar estoque real|

## Versão de45minutos

| Tempo | O que fazer |
|---|---|
|0–5|História, diagrama do fluxo, maturidades e políticas de acesso|
|5–13|RAG + MCP sobre catálogo, garantia e reposição; cliente escolhe produto|
|13–19|Inspecionar trace, parâmetros, fonte da previsão e prompt versionado|
|19–25|Gateway, AuthPolicy e testes positivos/negativos; chamadas de ferramentas reais|
|25–31|NeMo checks; se IPP passou seu gate, bloqueio no caminho MCP e prova de ausência de execução no backend|
|31–36|EvalHub: descobrir provider, submeter smoke limitado e abrir uma execução anterior completa|
|36–40|OpenShell somente se validado; caso contrário, aprofundar limitações dos rails/avaliações com evidências|
|40–43|GitOps: alteração sintética de ponto de reposição, revisão do diff, sync e rollback|
|43–45|Cliente repete fluxo e localiza seu resultado/trace|

## Perguntas de test drive

- “Consulte o estoque do AS-001 e proponha uma quantidade de reposição. Explique qual previsão e política foram usadas. Não crie pedidos.”
- “Qual é a política de entrega e qual documento sustenta a resposta?”
- “O que mudou entre a execução anterior e esta avaliação?”

No teste NeMo independente, use `cliente@example.invalid` e `DEMO_SECRET_AURORA`. Identifique que os dados são fictícios e que as expressões são regras demonstrativas. Uma frase alternativa que não combina com regex pode passar; isso é uma limitação observável, não motivo para ocultar o teste.

## O que significa pronto

- Ferramentas retornam os SKUs reais das fixtures; há versão dos dados e nenhum pedido é criado.
- Gateway rejeita ausência de token e identidade não permitida; backend privado não é um atalho acessível.
- NeMo permite e bloqueia os casos definidos; erro do checker não é confundido com bloqueio.
- Trace nova e execução EvalHub real são acessíveis com a identidade correta.
- Se IPP não foi validado, o roteiro descreve checks independentes e não proteção automática do MCP.
- Se OpenShell não foi validado, permanece addon experimental documentado.
- `maas-how-to` e os modelos/demos anteriores continuam saudáveis.

Links operacionais: [MCP](../labs/mcp.md), [Guardrails](../labs/guardrails.md), [Red teaming e OpenShell](../labs/red-teaming.md).
