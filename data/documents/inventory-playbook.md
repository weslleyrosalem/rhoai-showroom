# Procedimento de estoque — Aurora Supply
ID da fonte: inventory-playbook.md. Revisão fictícia 1.0.

A cobertura alvo de estoque é 21 dias. Cobertura inferior a sete dias gera alerta
para o comprador. O saldo vigente deve ser consultado na ferramenta de estoque;
este documento não contém saldos em tempo real.

A previsão de demanda informa a origem temporal, o horizonte e a versão do modelo.
Os dados do showroom são sintéticos e históricos. Nunca afirmar que são vendas reais
ou que a origem temporal da previsão corresponde ao dia atual.

Para recomendar reposição, consultar SKU, saldo, previsão e prazo do fornecedor.
Calcular quantidade sugerida como máximo entre zero e a diferença entre demanda
estimada para 21 dias e saldo atual. Arredondar para unidade inteira acima.
Se o modelo ou o SKU não estiver disponível, informar a ausência sem inventar valores.
