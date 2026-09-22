---
title: AutoML de demanda
---
# Outro caminho para o mesmo modelo de negócio

AutoML é Technology Preview no RHOAI3.5. O pipeline server do showroom habilita managed pipelines. Para iniciar a experiência nativa, a flag `spec.dashboardConfig.automl` deve estar ativa e o dataset deve existir em uma conexão S3 do projeto.

No Workbench, após instalar boto3:

```bash
python scripts/science.py upload
```

Abra Develop and train → AutoML → `ai-showroom` → Create optimization run. Use `aurora-data/demand.csv`, tarefa Time series forecasting, timestamp `date`, ID `sku`, target `units`, prediction length `7`. Selecione até três modelos no primeiro ensaio. Não use informação futura desconhecida como covariável conhecida.

Acompanhe o run e abra um resultado concluído: leaderboard, validação temporal e notebook gerado. Compare com a baseline do Ray usando a mesma janela de teste antes de afirmar ganho. O vencedor pode futuramente publicar o mesmo contrato JSON consumido pela ferramenta MCP; não há conversão automática implícita nesta entrega.

Recursos mínimos documentados: 4 CPUs e16Gi disponíveis. Execute sequencialmente com AutoRAG no perfil compacto. A presença da página ou do DSPA não significa que uma otimização já concluiu.

[Criação de AutoML](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_automl/creating-automl-optimization-run_automl).
