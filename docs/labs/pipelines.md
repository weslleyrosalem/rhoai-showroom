---
title: Pipeline de dados a modelo
---
# Um DAG com quality gate

`notebooks/aurora_pipeline.py` define três componentes KFP: preparar dados, treinar e aprovar o artefato. O treinamento usa o mesmo código do laboratório Ray, mas este DAG executa a variante CPU local; não atribua paralelismo Ray ao pipeline sem adaptar sua etapa de treino.

Compile na raiz do repositório:

```bash
pip install kfp==2.15.2
python notebooks/aurora_pipeline.py
```

Importe `notebooks/aurora_pipeline.yaml` no pipeline server `showroom-pipelines` de `ai-showroom`. Crie um run com `source_ref` apontando para o SHA do commit que deseja reproduzir. O padrão `main` facilita o primeiro test drive; SHA imutável é preferível para comparação.

O DAG gera dados CC0, mede modelos e só produz o artefato aprovado se o gate passar. O DSPA foi configurado com MLflow AUTODETECT e injeção de variáveis; confira os runs pai/filhos no workspace e o armazenamento de artefatos S3.

Não há deploy automático de modelos neste exemplo: publicar um artefato aprovado e atualizar o serviço consumidor são passos distintos. Mostre a promoção GitOps como mudança revisável quando o contrato de serving estiver validado.

Aceite: DAG Succeeded, artefatos baixáveis, métricas medidas e gate que realmente falha para um artefato reprovado. [Pipelines e MLflow](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_ai_pipelines/tracking-pipeline-experiments-with-mlflow_ai-pipelines).
