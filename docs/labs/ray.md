---
title: Treinamento CPU com Ray
---
# Dois workers, um artefato de previsão

O job usa um head e dois workers CPU. Cada worker treina quatro SKUs. O script verifica que resultados vieram de dois pods distintos; se não vierem, falha. Não solicita GPU e preserva o Llama em funcionamento.

Na raiz do repositório, em terminal autenticado:

```bash
oc create -f gitops/components/science/rayjob.yaml
oc get rayjobs,rayclusters,pods -n ai-showroom
```

O código clona o repositório público e instala versões fixas de MLflow e boto3. O primeiro início inclui download de imagem/dependências; prepare a imagem antes da apresentação. O tempo limite é 30 minutos. Após concluir, o cluster efêmero é removido após cinco minutos; o RayJob e os resultados no MLflow/S3 permanecem.

No MLflow, abra `aurora-demand`. Veja o run pai, os oito filhos, o hostname do worker, MAE e baseline. O artefato publicado é `s3://aurora-artifacts/models/forecast/latest.json`, com versão de modelo e ID de run.

Uma segunda execução precisa de um novo nome de RayJob. Copie o manifesto e altere `metadata.name`; não mantenha jobs de demonstração sob reconciliação que os recrie continuamente.

Para teste local sem cluster:

```bash
python3 scripts/science.py generate
python3 scripts/science.py train
python3 -m unittest discover -s tests -p test_science.py
```

Este laboratório demonstra treinamento distribuído por tarefas, não DDP ou treinamento multi-GPU. [Ray em OpenShift AI](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_distributed_workloads/running-ray-based-distributed-workloads_distributed-workloads).
