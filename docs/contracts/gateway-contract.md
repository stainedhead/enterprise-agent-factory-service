# Gateway contract: `afs-gateway` ↔ agents and the Agentic Teammates runtime

| | |
|---|---|
| **Status** | Contract v1.0.0, draft for implementation (2026-11-21); root PRD decision D28 |
| **Provider** | [enterprise-agent-factory-service-restapi](https://github.com/stainedhead/enterprise-agent-factory-service-restapi) (`afs-gateway`) |
| **Consumers** | Agents and pool workers in team namespaces; the Agentic Teammates runtime and its harnesses |
| **Requirements** | [Root PRD](../../enterprise-agent-factory-service-initial-PRD.md) BUD-2, BUD-3, AGT-4, SEC-6, TAG-4, IF-5; [database contract](database-contract.md) §4.2 for the spend functions |

## 1. Purpose

`afs-gateway` is the only path from an agent to Amazon Bedrock. It authenticates the calling pod,
checks the model is enabled for the team, reserves the worst-case cost against the team's budget,
forwards the call to the team's Bedrock application inference profile, settles to the actual cost and
records usage. Agents' own IAM roles never hold `bedrock:*`, so the gateway cannot be bypassed.

This contract fixes what an agent may rely on, so that standard Bedrock and Anthropic SDKs work with
**zero change to the agent's container** (SEC-6): the endpoint and credential arrive as environment
variables and a file.

## 2. Endpoints

Base URL: `AFS_GATEWAY_URL` (in-cluster, `https://afs-gateway.afs-system.svc:8443`, TLS with the
cluster's CA bundle mounted at `/var/run/secrets/afs/gateway/ca.crt`).

| Path | Compatible with | Streaming |
|---|---|---|
| `POST /model/{modelId}/converse` | Bedrock Runtime `Converse` | No |
| `POST /model/{modelId}/converse-stream` | Bedrock Runtime `ConverseStream` | Yes, AWS event stream (`application/vnd.amazon.eventstream`) |
| `POST /model/{modelId}/invoke` | Bedrock Runtime `InvokeModel` | No |
| `POST /model/{modelId}/invoke-with-response-stream` | Bedrock Runtime `InvokeModelWithResponseStream` | Yes, AWS event stream |
| `POST /anthropic/v1/messages` | Anthropic Messages API (`model` in the body) | Yes, server-sent events when `"stream": true` |
| `GET /healthz` | none | No |

`modelId` (or `model`) is the **AFS model id** from `ListModels`. The gateway maps it to the team's
application inference profile for that model. A model not enabled for the team → `403 AccessDenied`.
Request and response bodies are passed through unchanged except that the gateway sets
`requestMetadata` (§6) and may cap `maxTokens` (§4). Unsupported Bedrock operations (for example
`ApplyGuardrail`, batch jobs) → `404 NotFound`.

## 3. Authentication and delivery to the pod

| Item | Value |
|---|---|
| Credential | Projected ServiceAccount token, audience `afs-gateway`, lifetime 1 hour, rotated by the kubelet, file `/var/run/secrets/afs/gateway/token` |
| Header | `Authorization: Bearer <token>`. For Bedrock SDKs that sign with SigV4, the gateway also accepts the token in `X-Afs-Gateway-Token` and ignores the signature |
| Validation | Kubernetes TokenReview (cached for the token's remaining life, at most 5 minutes); yields namespace, ServiceAccount and pod name, hence team, agent or pool, and worker pod |
| Environment | `AFS_GATEWAY_URL`; `AWS_ENDPOINT_URL_BEDROCK_RUNTIME` = `AFS_GATEWAY_URL`; `ANTHROPIC_BASE_URL` = `AFS_GATEWAY_URL` + `/anthropic`; `AFS_GATEWAY_TOKEN_FILE` = the token path; `AFS_TAGS` (§6) |

Clients that cannot read a token file use the Agentic Teammates runtime helper, which reads the file
and sets the header. Whether an environment-only credential is also needed is open question OQ-3.

## 4. Reservation math

Before forwarding, the gateway reserves the worst-case cost with
`afs.reserve_spend_held(budget_id, period_start, amount, holder)` (holder = the calling pod; returns a reservation `uuid` or NULL), after
`afs.ensure_spend_counter(budget_id, period_start)` so a new period never blocks calls (D31).

```
output_tokens_max = request maxTokens (Converse inferenceConfig.maxTokens, Anthropic max_tokens)
                    else models.max_output_tokens
input_tokens_est  = ceil(request body bytes / 3)
reserve_usd       = output_tokens_max × output price per token
                  + input_tokens_est  × input price per token
```

Prices are the model's effective `model_prices` row at the time of the call. A request whose
`maxTokens` exceeds `models.max_output_tokens` is capped to it. On completion (or stream end, client
disconnect or error) the gateway calls `afs.settle_reservation(id, budget_id, period_start, actual_usd)`,
always with the budget and period it reserved against, with the cost from the response's usage (input,
output, cache read and cache write tokens). It returns false when the hold had already been released,
and the actual cost is still added, so a call that runs past the TTL still counts. A reservation never settled (for
example a gateway crash) expires after service setting `gateway.reservation_ttl_seconds` (default 900)
and is released by the reconciler. Spend can exceed the cap only where a call's actual cost exceeds its
reserved worst case, at most one in-flight call per agent or pool worker.

## 5. Streaming

The gateway forwards stream events as they arrive and adds less than 25 ms (p99) to the time to first
byte. The reservation is held for the whole stream. Usage is taken from the final metadata event
(`metadata.usage` for Converse, `message_delta.usage` for Anthropic). If the client disconnects, the
gateway cancels the upstream call and settles to the tokens reported so far, or to the reservation when
none are reported.

## 6. Tags in `requestMetadata`

The gateway sets Bedrock `requestMetadata` on every call, at most **16** pairs (D27): system tags first
(`afs-team-id`, `afs-agent-id` or `afs-pool-id`), then service fixed and required tags, then team tags in
key order, until 16. Keys that do not fit are listed on the team's cost tags page (T13). Any
`requestMetadata` the agent sent is replaced. The pod also receives its tags in `/etc/afs/tags.json`
and `AFS_TAGS` (TAG-4); the gateway does not read them from the request.

## 7. Errors

Errors use the API contract's body, `{"code", "message", "requestId", "details"}`, with JSON content
type, also on streaming paths when the error happens before the first event. After the first event, an
error ends the stream with an `exception` event (Bedrock) or an `error` event (Anthropic) that carries
the same `code`.

| HTTP | `code` | When | Retry |
|---|---|---|---|
| 400 | `ValidationError` | Malformed request, unknown model id format | No |
| 401 | `Unauthenticated` | Missing, expired or unknown token; a token from a deleted team's namespace | After refreshing the token file |
| 402 | `BudgetExceeded` | The reservation does not fit under the cap; `details` has `budgetId`, `period`, `remainingUsd` | No. Not `429`, so SDKs do not retry it |
| 403 | `AccessDenied` | Model not enabled for the team; team suspended (`details.reason = team_suspended`) | No |
| 404 | `NotFound` | Unsupported path or operation | No |
| 413 | `ValidationError` | Body over 20 MB | No |
| 429 | `Throttled` | Bedrock throttled the call (passed through with `Retry-After`) | Yes, with backoff |
| 502 | `UpstreamError` | Bedrock returned a server error; the reservation is released | Yes, with backoff |
| 503 | `Unavailable` | The gateway cannot reserve (database unavailable): it fails closed and forwards nothing | Yes, with backoff |

The reconciler's IAM explicit deny on the team's Bedrock role (BUD-3) is a backstop and is never seen
by agents, who have no Bedrock permission of their own.

## 8. Usage records

One `afs.usage_events` row per call, written in batches (at most 1 s delay). Columns as in the schema
(000001, 000011, 000012):

| Column | Meaning |
|---|---|
| `team_id`; `agent_id` or `pool_id` with `worker_pod` | Who called (pool workers carry their pod name) |
| `model_id` | AFS model id |
| `outcome` | `ok`, `error`, `rejected_budget` (`402`) or `rejected_model` (`403`) |
| `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens` | From the response usage |
| `cost_usd` | Settled actual cost (zero for rejected calls) |
| `latency_ms` | Total latency as the gateway saw it |
| `tag_set_id` | Snapshot of the team's tags at call time (TAG-6) |
| `request_id`, `occurred_at` | For support and the five-minute activity windows |

The reserved amount lives in `afs.spend_reservations`; the operation name and gateway overhead are
metrics, not columns. Rejected calls are recorded so reports can show them (RPT-3). No prompt or
completion content is stored or logged.

## 9. Versioning

Every response carries `X-Afs-Gateway-Contract-Version: <semver>`. New compatible paths, fields or
error codes are minor changes. Changing the authentication, the environment variable names or the error
codes of §7 is a major change and needs an ADR in the root and a transition period in which both forms
work.

## 10. Change process

1. Propose the change in this document in a `-restapi` PR labelled `contract`, with the gateway code
   and its tests.
2. Notify the Agentic Teammates project; a major change waits for its runtime release.
3. A conformance suite in `-restapi` runs the official Bedrock and Anthropic SDKs against the gateway
   with a fake Bedrock, covering every path, streaming, every error of §7 and the reservation math.
