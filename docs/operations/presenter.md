# Prepare a presentation

Open with one question: **“How does Aurora turn documents, inventory, and forecasts into a replenishment decision we can explain and operate?”** Choose the journey that fits the audience and keep the shared architecture visible.

Use the [inference script](../demos/inference.md), [MaaS script](../demos/maas.md), and [native screen tour](screen-tour.md) for the scheduled sessions and optional deep dives.

## Before the session

- Check the [validation record](validation.md), MaaS key expiration, operators, and endpoints.
- Warm up the models and GPU capacity you will use. Download weights and provision nodes before the session.
- Run a RAG question, MCP tool call, safety check, short evaluation, and Ray forecast.
- Test the participant's restricted identity. The presenter's admin session does not demonstrate visitor RBAC.
- Open the guide, OpenShift AI, MLflow, observability, and Argo CD. Use synthetic inputs throughout.
- Keep measured benchmark artifacts with their date and configuration. If a live experiment fails, identify earlier results as earlier results.

## Three ways to tell the story

| Audience | Opening | Main demonstration | Test drive |
|---|---|---|---|
| Security | Proposal with sources and tools | Allowed request, blocked request, and trace | Change the prompt and inspect the decision |
| Platform | Consumer with a key and quota | Governed endpoint, capacity, and metrics | Exhaust a short quota and observe recovery |
| DS/MLE | Demand history and baseline | Ray, quality gate, MLflow, and forecast-backed RAG | Change a hypothesis and compare results |

For 20 minutes, follow one journey's main path. For 45 minutes, add a controlled comparison and Workbench exploration. Keep a business decision at the center instead of visiting every screen.

## Use precise claims

“This result was measured on this hardware and workload.” “This capability is Technology Preview in 3.5.” “Replicas distribute requests; tensor or pipeline parallelism divides a model's work.” “MCP discovery filtering does not replace authorization.” “L40S does not support MIG; that lab requires compatible hardware.”

## Give the customer a repeatable experience

Share this guide and an appropriately scoped, time-limited identity. Participants can repeat authorized labs, inspect acceptance criteria, and deploy their own fork. The public site contains only synthetic examples and documentation; cluster access remains authenticated.
