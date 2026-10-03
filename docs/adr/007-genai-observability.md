# ADR-007: Compare OpenTelemetry, MLflow, and Phoenix for GenAI Observability

- Status: Proposed
- Date: 2026-10-03
- Owners: Abox laboratory team

## Context

Laboratory 7 requires reviewing the OpenTelemetry, MLflow, and Phoenix
interfaces; collecting traces from an agent; and comparing the three solutions
from a GenAI observability perspective.

The selected workload is the kagent `k8s-agent`. Its OpenTelemetry tracing was
enabled and configured to export OTLP/gRPC traces through the OpenTelemetry Demo
Collector. The downstream MLflow Collector routes traces from the `kagent`
namespace to MLflow experiment `kagent-lab7` and Phoenix project
`kagent-lab7`.

The detailed experiment record and screenshots are maintained in the
[Laboratory 7 report](../reports/lab7-genai-observability.md).

## Current evidence

MLflow successfully received agent traces and presented GenAI-specific
analytics. The captured interface includes trace status and duration, token
usage, latency, error rate, model attribution, and estimated cost.

![MLflow token and cost analytics](../assets/lab7/mlflow-token-cost.png)

At the same time, no traces were visible in Phoenix. This is currently treated
as an unresolved ingestion or routing issue, not as evidence that Phoenix lacks
the corresponding GenAI capabilities.

## Decision

No final solution preference is recorded yet. Keep OpenTelemetry as the common
instrumentation and transport layer, and evaluate MLflow and Phoenix as
specialized GenAI analysis backends using the same agent workload and test
requests.

The decision will be finalized only after the same traces are visible in both
backends. Comparison criteria will include:

- trace and span hierarchy;
- prompt, response, and tool-call visibility;
- token and cost accounting;
- latency and error analysis;
- evaluation and issue-detection features;
- filtering, project organization, and operator usability;
- compatibility with standard OpenTelemetry data.

## Consequences

- MLflow is already validated as a working destination for the selected agent.
- Phoenix remains under investigation and cannot yet be compared fairly.
- OpenTelemetry remains necessary independently of the eventual UI choice,
  because it decouples agent instrumentation from the analysis backend.
- A final Accepted ADR will require matching evidence from Phoenix and a
  completed feature-by-feature comparison.

## Open questions

1. Does the Phoenix exporter fail at transport, schema ingestion, or project
   assignment?
2. Are OpenInference semantic attributes required beyond
   `openinference.project.name` for useful Phoenix rendering?
3. Which backend provides clearer representation of nested agent and tool-call
   spans?
4. Are token and cost calculations consistent between MLflow and Phoenix for
   the same trace?

