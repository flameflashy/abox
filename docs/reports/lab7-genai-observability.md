# Laboratory 7: GenAI Observability Comparison

- Date: 2026-10-03
- Status: In progress
- Agent under test: kagent `k8s-agent`
- MLflow experiment: `kagent-lab7` (experiment ID `2`)
- Phoenix project: `kagent-lab7`

## Objective

Compare standard OpenTelemetry, MLflow, and Phoenix as observability solutions
for a GenAI agent. The experiment uses the same OpenTelemetry traces emitted by
`k8s-agent` and attempts to deliver them to both MLflow and Phoenix.

## Telemetry path

The agent exports OTLP/gRPC traces to the OpenTelemetry Demo Collector. The
Collector forwards them to the MLflow Collector, which routes traces from the
`kagent` namespace to two backends:

1. MLflow experiment `kagent-lab7`;
2. Phoenix project `kagent-lab7`, selected with the
   `openinference.project.name` resource attribute.

The active `k8s-agent` deployment reported `OTEL_TRACING_ENABLED=true` and used
`http://otel-collector.otel-demo.svc.cluster.local:4317` as its OTLP trace
endpoint.

## Current results

### MLflow

MLflow received and displayed the agent traces successfully. The trace list
contained successful spans and a complete agent interaction with a duration of
approximately 3.792 seconds and 7,285 tokens.

![MLflow trace list](../assets/lab7/mlflow-traces.png)

The experiment overview showed incoming trace activity, an aggregate latency of
160.85 ms for the selected period, and no reported errors.

![MLflow usage, latency, and errors](../assets/lab7/mlflow-overview.png)

The GenAI-specific view calculated 10.02K tokens in total (9.87K input and 144
output), an average of 5.01K tokens per trace, and an estimated total cost of
$0.00418. The recorded model was `gpt-4.1-mini`.

![MLflow token and cost analytics](../assets/lab7/mlflow-token-cost.png)

These results demonstrate that MLflow understands enough of the exported span
semantics to derive GenAI-oriented usage and cost metrics, rather than merely
storing generic OpenTelemetry spans.

### Phoenix

No traces were visible in Phoenix at the time of the same test, even though the
MLflow Collector configuration contained the `otlp_grpc/phoenix` exporter and
the `traces/kagent` pipeline referenced it. Therefore the experiment currently
proves successful trace generation and delivery to MLflow, but does not yet
prove successful delivery to Phoenix.

This is an active diagnostic item. The Phoenix result must not be interpreted
as a product comparison until exporter logs, endpoint reachability, protocol
compatibility, and project assignment have been checked.

## Preliminary comparison

| Solution | Result so far | GenAI value observed |
|---|---|---|
| Standard OpenTelemetry | Agent spans are generated and routed through OTLP | Vendor-neutral collection and routing; raw span-level evidence |
| MLflow | Traces visible in experiment `kagent-lab7` | Trace navigation, token usage, latency, errors, model attribution, and estimated cost |
| Phoenix | No traces visible yet | Not yet assessable; ingestion must be repaired or verified first |

## Remaining work

1. Inspect the MLflow Collector exporter logs for Phoenix delivery failures.
2. Verify OTLP/gRPC connectivity to `phoenix-svc.phoenix.svc.cluster.local:4317`.
3. Confirm that Phoenix accepts the emitted OpenTelemetry schema and assigns
   spans to project `kagent-lab7`.
4. Capture matching Phoenix trace and project screenshots after ingestion works.
5. Compare trace hierarchy, prompts/responses, tool calls, token accounting,
   latency, errors, evaluation features, and usability across all three tools.

