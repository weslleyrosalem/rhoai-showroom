# Test drive

Choose an experience and confirm the lab prerequisites. Use `ai-showroom` and synthetic data. Give each participant an appropriate identity; never share the presenter's administrator session.

## 1. Ask for an answer with evidence

In the Playground or Aurora application, try:

> Prepare next week's replenishment proposal. Check inventory for AS-001, compare it with the forecast, and cite the policy you used. Prepare a proposal only; do not place an order.

Observe the tool calls, supporting documents, and forecast. The answer should distinguish inventory facts, statistical forecasts, and the LLM's explanation.

**Change one thing:** choose another SKU. Confirm that the tool queried that SKU and that the sources remain relevant. Open the trace for the new question.

## 2. Test an access boundary

Follow [MCP and tools](../labs/mcp.md). Make one authorized request and one request without credentials. The first should work; the second should fail authentication.

A shorter VirtualServer tool list does not prove authorization. Compare discovery with execution and verify that access controls protect the actual call.

## 3. Try a quota

Follow [MaaS and quotas](../labs/maas.md). Use a key bound to the limited subscription. Observe a successful response, accounting, HTTP 429, and recovery after the window. Make a control request using another subscription.

**Change one thing:** increase the prompt length. Observe input and output tokens. A token quota does not correspond to a fixed number of requests.

## 4. Change a training hypothesis

Open the Aurora notebook in the [Workbench](../labs/workbench.md). Change an experiment parameter, run the small training job, and compare temporal holdout error against the baseline.

Record parameters and results in MLflow. Do not select a model based only on training error. A published artifact must identify its version, forecast horizon, and source run.

## 5. Watch a GitOps change arrive

On a branch of your fork, change a synthetic policy or demonstration setting. Review the diff before synchronization. After sync, repeat the question that depends on the changed data and inspect the version used.

Follow [Reset the test drive](reset.md) when finished. Reverting a presentation change should not delete experiment data, operators, or shared models.

## What the experience demonstrates

You should be able to connect a question with access controls, a subscription, source documents, tools, a model, and execution evidence. Shared backend service-account traces do not provide individual visitor attribution by themselves.
