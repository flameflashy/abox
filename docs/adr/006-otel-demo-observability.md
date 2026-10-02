# ADR-006: Evaluate the OpenTelemetry Demo Without the Unavailable Triage Backend

- Status: Accepted
- Date: 2026-10-02
- Owners: Abox laboratory team

## Context

Laboratory 6 requires deploying the `feat/otel-demo` branch, reviewing the
OpenTelemetry Demo architecture, exercising the demo product, and recording
questions and observations from an observability perspective. Integrating the
existing agents and kagent setup is optional.

The branch deployed OpenTelemetry Demo chart `0.41.2` successfully. The
application namespace contained all expected demo workloads, including two
`otel-collector-agent` Pods, one on each worker node. After 58 minutes, every
application container was Ready and Running with zero restarts. The
`opentelemetry-demo` HelmRelease was Ready with a successful installation
status.

The branch also references a Triage observability stack. Its Flux sources could
not be reconciled because the required OCI artifacts were private and the
cluster did not have `ghcr-credentials`. The instructor explicitly directed
students to skip Triage until an open-source version becomes available.

The standard OpenTelemetry Demo architecture includes Prometheus, Jaeger,
OpenSearch, and Grafana as telemetry backends and user interfaces. Those
services were not present in this deployment, although the frontend proxy and
Collector configuration still referenced them.

## Decision

Evaluate the deployed branch as provided, with Triage excluded from the scope.
Do not create credentials for private Triage artifacts and do not add an
independent Grafana, Jaeger, Prometheus, or OpenSearch installation for this
laboratory. Adding a replacement backend would change the system under test and
would no longer represent the supplied branch.

Use the following evidence sources instead:

- Kubernetes Pod, HelmRelease, Service, EndpointSlice, and Event status;
- manual user journeys through the demo storefront;
- the built-in feature flag and telemetry coverage pages;
- k6 load-generator progress;
- application and OpenTelemetry Collector logs;
- HTTP status and redirect behavior through `frontend-proxy`.

Treat Kubernetes readiness and end-to-end telemetry delivery as separate
properties. A Ready Collector process does not demonstrate that telemetry was
successfully exported, stored, or made queryable.

## Test method

The product test covered the following user journey:

1. Open the storefront and browse multiple products.
2. Add products to the cart and change quantities.
3. Complete checkout through the simulated purchase confirmation.
4. Verify that the feature flag page is reachable and inspect the available
   controlled-failure scenarios.
5. Open the telemetry documentation page and review signal coverage across the
   polyglot services.
6. Compare workload readiness, restarts, events, and load-generator progress
   after the interaction.

The load generator was evaluated from its logs rather than from a browser UI.
The deployed component is a headless k6 process, even though the chart creates
a Service on port 8089 and the frontend proxy exposes a `/loadgen/` route.

## Results

### Product and workload health

| Check | Observed result |
|---|---|
| Helm release | `opentelemetry-demo`, chart `0.41.2`, Ready `True` |
| Application Pods | All Ready and Running |
| Container restarts | Zero |
| `/` | HTTP 200 |
| `/feature` | HTTP 200 |
| `/telemetry/` | HTTP 200 |
| Storefront journey | Browse, cart update, and checkout completed |
| k6 workers | 6/6 virtual users |
| k6 progress | Increased from more than 2,500 to 3,244 completed iterations |
| Interrupted k6 iterations | Zero |

The Kubernetes Events inspected after the test contained normal image pull,
container start, and Helm installation events. They did not report application
container failures.

### Published routes without working user interfaces

| Route | Observed result | Interpretation |
|---|---|---|
| `/grafana/` | HTTP 503 | Grafana Service is absent |
| `/jaeger/ui/` | HTTP 503 | Jaeger Service is absent |
| `/loadgen/` | HTTP 308 to `/loadgen` | The upstream emits a redirect |
| `/loadgen` | HTTP 404 | The proxy does not route the redirect target |

The `load-generator` Service selected endpoint `10.244.1.41:8089`, but direct
port-forwarding failed with `connection refused`. The container declared port
8089 but did not listen on it because the deployed k6 workload runs headlessly.
This demonstrates that a Service endpoint only confirms Pod selection; it does
not prove that a process is accepting connections on the target port.

### Telemetry pipeline

Collector logs confirmed that the applications and load generator attempted to
send telemetry. End-to-end export was not operational:

| Signal | Configured destination | Observed behavior |
|---|---|---|
| Logs | OpenSearch | DNS lookup failed; data was rejected as a non-retryable permanent error |
| Metrics | Prometheus OTLP endpoint | DNS lookup failed; the exporter continued retrying |
| Traces | Jaeger OTLP endpoint | Export failed with `Unavailable`; the exporter continued retrying |
| Kubernetes node metrics | kubeletstats receiver | TLS verification failed because the Kind kubelet certificate did not contain the node IP in its SANs |

The OpenSearch exporter explicitly reported rejected items and recommended
enabling a sending queue. The missing backends also created backpressure. The
Collector logged `data refused due to high memory usage`, failed Prometheus
scrape commits, and timed-out internal metric uploads. Therefore some telemetry
was already being rejected or lost during the test.

Both Collector Pods remained Ready despite the failed exporters, receiver
errors, and memory pressure. The HelmRelease also remained Ready because Helm
installation health describes Kubernetes resource deployment, not telemetry
pipeline correctness.

## Alternatives considered

### Authenticate to the private Triage artifacts

Rejected for this laboratory. The required artifacts are not currently part of
the public student setup, and the instructor explicitly directed students to
skip Triage.

### Install the standard observability backends independently

Rejected for the recorded experiment. This would consume additional Codespace
resources and change the supplied configuration. It would also hide the
configuration inconsistency that the experiment is intended to observe.

### Evaluate only Kubernetes readiness

Rejected as insufficient. It would incorrectly classify the observability
system as healthy even though logs, metrics, and traces could not reach their
configured destinations.

## Consequences

- The laboratory verifies product behavior, telemetry generation, Collector
  intake attempts, and failure handling, but it does not validate stored or
  queryable traces, metrics, or logs.
- Trace navigation, metric dashboards, and log-to-trace correlation cannot be
  evaluated until an observability backend is deployed.
- The missing backends produce continuous retries and memory pressure in the
  Collector, so long-running tests can lose telemetry even while application
  Pods remain healthy.
- Proxy routes and Services should not be treated as proof that their upstream
  interfaces are available.
- A later experiment can repeat the same user journey after the public Triage
  stack is available and compare end-to-end signal delivery.

## Observability questions

1. Should Collector readiness include the availability of required exporters,
   or should a separate pipeline-health signal be exposed?
2. Should the deployment disable exporters and proxy routes when their backend
   services are not installed?
3. Which telemetry is dropped after retry queues fill, and what retention or
   persistent-queue policy is required?
4. How should an operator discover telemetry loss when the observability
   backend itself is unavailable?
5. Why is port 8089 published for the load generator when the deployed k6
   process does not listen on it?
6. Should the Kind-specific kubeletstats configuration skip TLS verification or
   use a certificate endpoint with a valid SAN?
7. What signal coverage is required consistently across the demo's different
   implementation languages?

## References

- <https://github.com/den-vasyliev/abox/tree/feat/otel-demo>
- <https://opentelemetry.io/docs/demo/architecture/>
- <https://opentelemetry.io/docs/demo/feature-flags/>

