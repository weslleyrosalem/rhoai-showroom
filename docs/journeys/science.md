---
title: Dados, modelos e decisões
---
# Data Scientist e ML Engineer

A Aurora Supply precisa recomendar reposição de estoque. A previsão vem de um modelo treinado, o saldo vem de uma ferramenta MCP, e a política vem dos documentos. A resposta conecta as três fontes e prepara uma proposta para aprovação humana.

Todos os produtos, políticas e dados de vendas são fictícios. A série cobre 2025: a previsão é histórica e serve ao laboratório. Ela não representa a data atual nem uma decisão comercial real.

## Test drive de 20 minutos

| Tempo | Ação | Resultado a mostrar |
|---|---|---|
| 0–3 | Perguntar “Devo repor AS-001? Explique a aprovação.” | Resposta, fontes e ferramentas |
| 3–6 | Abrir `01-demand.ipynb` | Dados sintéticos e split temporal |
| 6–10 | Submeter o RayJob; abrir uma execução concluída | Dois workers CPU, modelo e métricas no MLflow |
| 10–13 | Comparar candidato e baseline | Um candidato perde e é rejeitado; não esconder esse resultado |
| 13–17 | Alterar pergunta/prompt e consultar novamente | Política citada e proposta sem compra |
| 17–20 | Abrir trace e avaliação | Relação entre experimento, modelo e resposta |

## Versão de 45 minutos

Acrescente exploração de dados, execução do pipeline, o ranking de um AutoML já concluído e a comparação de padrões AutoRAG. Inicie um run curto ao vivo; mantenha resultados anteriores reais para explicar etapas demoradas. Identifique claramente quando está mostrando uma execução histórica.

## Caminho técnico

`demand.csv → Ray por SKU → quality gate → MLflow/S3 → ferramenta MCP → RAG/LLM → avaliação/tracing`.

O modelo é uma regressão regularizada de tendência e sazonalidade. O último mês é holdout. Para cada SKU, o candidato só é escolhido se não piorar a baseline sazonal. A previsão de sete dias é um artefato JSON com versão e origem temporal.

O Ray distribui tarefas de treinamento entre workers. Isso não é DDP de gradientes. O aplicativo RAG usa recuperação lexical TF-IDF claramente identificada; o laboratório AutoRAG apresenta o caminho nativo com OGX, embeddings e banco vetorial.

## Laboratórios

- [Workbench](../labs/workbench.md)
- [Ray](../labs/ray.md)
- [MLflow](../labs/mlflow.md)
- [Pipeline](../labs/pipelines.md)
- [RAG](../labs/rag.md)
- [Avaliação](../labs/evaluation.md)
- [AutoML](../labs/automl.md)
- [AutoRAG](../labs/autorag.md)

Preparar a apresentação exige testar o fluxo, não apenas verificar pods Ready. O relatório de validação da instalação informa quais laboratórios passaram em execução real.
