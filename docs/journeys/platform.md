# Jornada Plataforma — operar a Aurora Supply

A Aurora Supply quer que seu assistente consulte políticas, estoque e previsões sem transformar cada equipe em operadora de infraestrutura. Nesta visita, o cliente assume o papel de engenheiro de plataforma: escolhe modelos, oferece uma API governada e mede o resultado.

A instalação de referência usa OpenShift AI **3.5.1**. Os manifests e scripts deste módulo foram preparados e tiveram validação de schema; isso não significa que benchmarks GPU, MIG ou modelos grandes já tenham sido executados. Consulte a evidência da instalação antes de apresentar cada etapa.

## Três níveis de visita

| Duração | História | Interação do cliente |
|---|---|---|
| 20 minutos | Escolher → consumir → limitar → observar | Filtrar o catálogo, fazer uma pergunta e atingir uma quota de teste |
| 45 minutos | A anterior + eficiência e escala | Repetir prefixos, comparar resultados medidos e interpretar TTFT/throughput |
| Laboratório | Reprodução completa | Alterar configuração em Git, sincronizar, executar ensaio e conferir evidências |

## Visita de 20 minutos

1. **0–3 min: mostrar o produto conectado.** Abra `ai-showroom`. Explique que a mesma Aurora Supply conecta RAG, estoque MCP, previsão de demanda e o assistente. Mostre a fronteira entre o projeto e os serviços compartilhados.
2. **3–6 min: curadoria.** Abra o catálogo e a fonte Qwen curada. O visitante escolhe um modelo incluído, lê a licença e confere o hardware profile. Um nome no catálogo não garante que haja GPU livre.
3. **6–10 min: test drive.** Faça uma pergunta sobre o estoque da Aurora pelo Playground. Mostre modelo, subscription e métricas. Na instalação que reutiliza a fundação existente, o backend é o Llama de `maas-how-to`; no perfil GPU novo, é `aurora-qwen-4b`.
4. **10–14 min: governança.** Use chaves criadas explicitamente para `showroom-test-drive` e `showroom-standard`. Demonstre 401 sem credencial, 200 autorizado, 429 no limite curto, premium ainda atendendo e recuperação após a janela. Nunca exponha a chave na tela ou em Git.
5. **14–18 min: operação.** Relacione a chamada aos contadores de tokens, latência e GPU. Identifique quais dados são desta execução e quais são de um ensaio anterior. Tracing de aplicação e métricas de infraestrutura respondem a perguntas diferentes.
6. **18–20 min: GitOps.** Mostre um diff pequeno e o recurso reconciliado. Explique que o catálogo compartilhado usa merge protegido contra concorrência e que credenciais pertencem ao ambiente.

## Extensão para 45 minutos

- **5 min:** escolher outro modelo do catálogo e examinar os recursos de uma implantação já aquecida.
- **8 min:** abrir a comparação Transformers/vLLM na mesma GPU, modelo, precisão e carga; olhar erros, TTFT e tokens/s.
- **7 min:** repetir prefixos em duas réplicas e confirmar atividade do Endpoint Picker. Comparar round-robin e llm-d sobre os mesmos oito dispositivos.
- **3 min:** distinguir TP4 em um nó, duas réplicas TP4 em dois nós e um único modelo repartido entre nós. Este último exige outro ensaio; não é demonstrado simplesmente por ter duas réplicas.
- **2 min:** explicar capacidade, autoscaling e a opção MIG. A L40S não suporta MIG; a alternativa usa A100 e outro perfil de infraestrutura.

## O que apresentar como produto e como laboratório

MaaS core, quotas e chaves são a fundação suportada. vLLM no MaaS, algumas integrações externas e WVA têm classificação Technology Preview. Hierarchical KV cache tiering é Developer Preview. Mostre o selo de maturidade no momento da demonstração; a versão da API Kubernetes não substitui essa informação. [Release notes 3.5](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/technology-preview-features_relnotes), [Developer Preview](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/developer-preview-features_relnotes).

## Preparação e critérios de sucesso

Execute os laboratórios de [hardware](../labs/hardware.md), [catálogo](../labs/model-catalog.md), [MaaS](../labs/maas.md) e [benchmark](../labs/benchmark.md). Tenha resultados datados, modelos prontos e corpus já carregado. Não espere provisionamento de worker ou download de dezenas de gigabytes durante a visita.

O ensaio só passa quando os caminhos realmente respondem, os acessos negativos são negados, a quota é observada, os recursos anteriores continuam saudáveis e o teto global de **16 GPUs físicas** é respeitado. Um módulo bloqueado por capacidade ou dependência aparece como bloqueado no guia e fica fora do roteiro ao vivo.
