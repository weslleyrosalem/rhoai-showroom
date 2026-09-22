---
title: Experimentos e traces com MLflow
---
# Evidência de como a resposta foi produzida

O operador gerencia o singleton `MLflow/mlflow` e seu serviço em `redhat-ods-applications`. O projeto `ai-showroom` é um workspace. O Secret de artefatos e `MLflowConfig` do projeto selecionam o bucket; nenhum segredo faz parte deste repositório.

O overlay showroom usa SQLite em PVC 5Gi para metadados e SeaweedFS S3 para artefatos. São escolhas de laboratório com uma réplica. Uma implantação permanente deve trocar esses serviços de exemplo por PostgreSQL e storage S3 adequados ao ambiente.

O endpoint interno testado é `https://mlflow.redhat-ods-applications.svc:8443/mlflow`. Clientes montam a CA de serviço do OpenShift e verificam TLS. O token de ServiceAccount é lido em memória; não é exibido no notebook, logs ou página.

- `aurora-demand`: treino, baseline, seleção e artefato de previsão.
- `aurora-assistant`: trace de recuperação, chamadas MCP e inferência MaaS.
- `aurora-model-safety`: resultados de avaliação do EvalHub.

Execute o notebook `01-demand.ipynb` para registrar um experimento. Consulte o app RAG para gerar trace. Abra o workspace no dashboard e confirme que o trace contém os spans, não apenas uma linha de log. Falha de integração gera erro; a aplicação não simula um resultado positivo.

MLflow base é GA. Algumas experiências integradas de Playground/prompt registry/tracing permanecem TP. MLflow e o Model Registry do RHOAI são produtos de registro distintos; esta entrega não pressupõe sincronização automática entre eles. [Configuração oficial](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_mlflow/installing-mlflow_mlflow).
