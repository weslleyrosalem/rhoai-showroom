# Avaliar segurança com EvalHub e Garak

Garak verifica como o modelo responde a probes adversariais; NeMo impõe rails no caminho escolhido; MCP Gateway governa o acesso às ferramentas. Os três controles têm funções diferentes. Um score de avaliação não certifica segurança universal.

O EvalHub3.5 oferece providers de avaliação, incluindo Garak, e guarda resultados com configuração/proveniência. Seu MCP server é Technology Preview e permite descobrir avaliações, submeter jobs e acompanhar resultados. [EvalHub](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/evaluating_ai_systems/evaluating-llms-with-evalhub_evaluate), [EvalHub MCP](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/evaluating_ai_systems/evalhub-mcp-server_evaluate).

## Preparação

- Modelo Aurora acessível por endpoint OpenAI compatível, com cota suficiente para o ensaio.
- EvalHub saudável, database persistente e identidade autorizada no tenant `ai-showroom`.
- MLflow disponível para armazenar runs/artefatos.
- Chaves em Secrets; nenhum token em JSON de job, Git, capturas ou prompts.
- Fixtures exclusivamente sintéticas e acesso limitado ao cluster autorizado.

Liste providers/benchmarks pela UI ou SDK da instalação. Use os IDs retornados por essa API: o nome do provider em ConfigMap/CR pode diferir do ID em uma requisição. Não copie um job antigo sem verificar o contrato atual.

## Experimento demonstrável

Crie duas execuções com o mesmo modelo, versão, parâmetros e conjunto de testes:

| Run | Alvo | O que medir |
|---|---|---|
|`aurora-baseline`|Endpoint do modelo|Resultados dos probes escolhidos|
|`aurora-guarded`|Endpoint de chat protegido, se efetivamente implantado|Os mesmos resultados, bloqueios, falhas e latência|

O endpoint `/v1/guardrail/checks` **não** é chat completions e não deve ser usado como alvo Garak OpenAI. Caso só os checks independentes estejam instalados, mostre a execução baseline no EvalHub e os testes determinísticos NeMo separadamente. Não invente uma comparação `guarded` que não foi executada.

Para o test drive ao vivo, escolha um benchmark rápido disponível, limite exemplos e registre esse limite. O benchmark `quick` do provider documentado serve como smoke, não como cobertura completa. Deixe uma execução completa anterior acessível com timestamp e parâmetros para não depender de uma avaliação longa durante a reunião.

Mostre: ID do job, status terminal, modelo/versão, benchmark/probes, número de amostras, métricas, duração, falhas, configuração e artefato. Compare medidas equivalentes; alterar prompt, amostra e endpoint ao mesmo tempo torna a atribuição do ganho ambígua.

## Critérios de aceite

1. O job de fato termina e o resultado é consultável na UI/API.
2. A configuração inclui amostragem, versões e identificação do endpoint sem segredos.
3. A métrica usada é explicada com sua direção; uma taxa de ataque bem-sucedido menor é melhor.
4. O cliente consegue repetir o smoke e encontrar seu próprio run.
5. Falha de rede, cota429 ou autenticação401 não é contabilizada como proteção bem-sucedida.
6. Uma comparação usa workloads equivalentes e distingue respostas bloqueadas de erros de infraestrutura.

## OpenShell: laboratório opcional

OpenShell é um runtime externo NVIDIA. Seu [Helm Kubernetes](https://docs.nvidia.com/openshell/kubernetes/setup) é experimental e exige Agent Sandbox controller/CRDs, além de autenticação de usuário para acesso compartilhado. Ele não é uma feature GA nativa do OpenShift AI.

Antes de incluí-lo na apresentação, valide em namespace separada `ai-showroom-sandbox`: UID não root compatível com SCC, ausência de privilégios amplos, isolamento de filesystem/processo, egress permitido/rejeitado, autenticação, persistência e limpeza. O [driver Kubernetes](https://docs.nvidia.com/openshell/reference/sandbox-compute-drivers) detecta UID/GID de namespace OpenShift, mas isso não substitui o teste no runtime ROSA efetivamente usado.

Demonstração condicionada: agente lê somente um arquivo sintético autorizado; tentativa de alcançar um destino fora da allowlist é bloqueada e observável. Não dê ao cliente permissões para criar pods/Sandbox CRs na namespace de isolamento. Enquanto esses critérios não forem executados, registre **laboratório pendente de validação**, nunca “sandbox seguro pronto”.
