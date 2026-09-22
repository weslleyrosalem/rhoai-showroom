# Restaurar o test drive

A unidade de restauração é o experimento, não o cluster inteiro. Nunca remova namespaces compartilhados, o DSC ou pools existentes para reiniciar a demonstração.

| Ação do participante | Restauração |
|---|---|
| Editou notebook | Descartar apenas alterações daquele notebook ou abrir cópia limpa do Git |
| Criou run Ray/MLflow | Preservar evidência; interromper somente job identificado e submeter novo run |
| Esgotou quota curta MaaS | Esperar a janela indicada; validar recuperação com a mesma subscription |
| Alterou prompt/configuração | Reverter commit ou repor versão conhecida e observar Argo |
| Subiu modelo GPU de experimento | Encerrar somente modelo próprio após salvar resultado; conferir inventário GPU/pools |
| Chave expirou | Emitir nova chave de duração limitada e atualizar Secret; não aumentar acesso |

O Argo está configurado com prune=false. Remover um YAML do Git não apaga o recurso. Exclusão de dados persistentes requer decisão explícita do responsável e backup adequado.

Antes de reduzir pool GPU, confirme que nenhum workload de outra equipe depende dele, que os pods Aurora foram movidos/parados e que a capacidade final respeita os limites. O pool com a inferência original é preservado. Não aplique os perfis L40S e MIG simultaneamente por conveniência: ambos contam para o teto físico.

Os dados comerciais originais ficam em `data/`; ConfigMaps MCP são derivados deles por `sync_data.py`. Para incorporar uma nova previsão, use o fluxo de publicação descrito em [Ray](../labs/ray.md), mantendo a origem do modelo e o run_id. Não edite à mão resultados para fazê-los parecer melhores.
