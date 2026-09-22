# Aurora Supply: uma única história

A Aurora Supply é uma distribuidora fictícia de equipamentos de escritório. Seu catálogo, estoque, documentos, histórico de demanda e casos de avaliação são sintéticos e versionados neste repositório.

O problema apresentado ao cliente é concreto: uma pessoa precisa escolher produtos, verificar disponibilidade, entender a política aplicável e preparar uma proposta de reposição. A proposta não executa pedidos ou pagamentos.

## O caminho da pergunta

| Etapa | Componente | Evidência que precisa aparecer |
|---|---|---|
| A pessoa faz uma pergunta | Playground ou aplicação Aurora | Prompt, modelo e assinatura selecionados |
| Recupera a política relevante | RAG | IDs de documentos e trechos usados |
| Consulta catálogo e estoque | MCP Gateway + Aurora Tools | `tools/list`, chamada real e valores do dataset |
| Consulta a previsão | Modelo treinado com Ray | Versão, horizonte, métricas de teste e run MLflow |
| Produz a explicação | Modelo local ou externo via MaaS | Resposta e consumo; provider identificado |
| Aplica controles | AuthPolicy, quota e NeMo | Testes positivos/negativos, status e motivo observável |
| Investiga o resultado | MLflow, métricas e Tempo | Trace nova ou série atual, com origem e intervalo |
| Evolui a experiência | Prompt, dados ou manifesto em Git | Diff, sync Argo CD, repetição e rollback |

As ferramentas retornam dados estruturados. O modelo não é a fonte de verdade para estoque, quota, preço ou previsão. Os testes comparam esses valores com os artefatos sintéticos.

## Contratos e nomes

| Nome | Finalidade |
|---|---|
| `rhoai-showroom` | Repositório e documentação pública |
| `ai-showroom` | Projeto principal exibido na interface |
| `ai-showroom-bench` | Cargas de benchmark que precisam de isolamento de agendamento |
| `aurora-tools` | Ferramentas MCP somente de consulta e proposta |
| `showroom-mcp` | Gateway e extensão MCP |
| `aurora-rag` | Aplicação que integra recuperação, ferramentas, LLM e traces |
| `aurora-lab` | Workbench para a jornada de ciência de dados |
| `showroom-s3` | Armazenamento compatível com S3 para dados e artefatos da demo |
| `mlflow` | Instância compartilhada gerenciada pela plataforma |
| `showroom-visitors` | Leitura e experiência de demonstração autorizada |
| `showroom-data-scientists` | Trabalho no projeto e execução dos laboratórios |
| `showroom-platform-admins` | Administração do projeto do showroom |

Operadores e serviços de plataforma permanecem em seus namespaces próprios. MLflow é um recurso singleton do cluster nesta versão; não há uma instância arbitrária por projeto. O projeto novo concentra a experiência, sem copiar componentes globais desnecessariamente.

## Perfis de capacidade

O núcleo usa CPU para ferramentas, recuperação, controle, experimentos e treinamento pequeno; a inferência pode reutilizar um endpoint MaaS existente. Os perfis GPU adicionam modelos e experimentos de serving.

O limite desta instalação é **16 GPUs físicas, incluindo pools existentes e capacidade temporária de upgrade**. Réplicas virtuais de time-slicing e partições MIG não aumentam esse número. O [préflight de capacidade](../labs/hardware.md) precisa passar antes de ativar um perfil.

L40S atende à demonstração de inferência e tensor parallelism. MIG exige hardware compatível, como A100/H100, e fica em um perfil alternativo. Os laboratórios não transformam time-slicing em MIG nem inferem eficiência apenas pelo número de GPUs.

## Três conversas sobre o mesmo ambiente

- **Segurança:** “Como eu limito o que um agente consegue consultar ou fazer, e como investigo uma decisão?”
- **Plataforma:** “Como eu publico, compartilho, dimensiono e acompanho modelos como serviços?”
- **Ciência de dados:** “Como eu provo uma hipótese, treino, avalio e transformo o resultado numa experiência útil?”

Ao mudar de jornada, mantenha a mesma pergunta de negócio. Isso permite mostrar como o dado treinado pelo cientista chega à ferramenta, como a plataforma atende à inferência e como a equipe de segurança verifica o fluxo.
