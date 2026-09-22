---
title: Workbench Aurora Lab
---
# Um ambiente de trabalho com contexto

Abra o projeto `ai-showroom`, Workbenches, `Aurora Supply — Data Science Lab`. A imagem CPU é a 3.5 do RHOAI, fixada por digest. O PVC de 10Gi preserva arquivos. O init container clona este repositório público somente se ele ainda não existir; não sobrescreve alterações do participante.

1. Abra `rhoai-showroom/notebooks/01-demand.ipynb`.
2. Execute as células de geração e treinamento.
3. Compare `candidate_mae` e `baseline_mae`; observe a seleção de modelo por SKU.
4. Execute a célula de MLflow/S3 depois de instalar as versões declaradas.
5. Abra `02-rag.ipynb` e consulte o aplicativo integrado.

O acesso ao notebook usa a autenticação injetada pelo controlador. O ServiceAccount `aurora-science` tem escrita de experimentos no projeto; não recebe permissão de administrador do cluster. Submeter o RayJob pelo terminal do apresentador evita conceder gestão ampla ao notebook.

Para atualizar uma cópia existente, primeiro revise mudanças locais e depois use `git pull` no terminal do notebook. Não apague o PVC para atualizar código.

Aceite: notebook Ready, acesso autenticado, arquivo persiste após reinício e um experimento verdadeiro aparece no MLflow. [Integração oficial](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_mlflow/tracking-experiments-with-mlflow-in-workbenches).
