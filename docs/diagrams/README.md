# Diagrams

Architecture diagrams for the Enterprise Agent Factory Service. Each one is generated from a small source
module in [source/](source/), so diagrams stay consistent and reviewable as code. Every diagram is committed
as SVG (used in the READMEs) and as a 2x PNG (for slides and documents).

| Diagram | Shows | Used in |
|---|---|---|
| [architecture-overview](architecture-overview.svg) | Clients, control plane, database, EKS tenancy, AWS services, and the team gateway in front of Bedrock and OpenAI-compatible providers (1.2.0) | Root README; copies in every child README |
| [model-gateway](model-gateway.svg) | A route call through the team gateway: admission, reserve, forward with the route credential, settle; provider cost pulls, statements and variance (1.2.0) | Root README, solution design |
| [mcp-gateway](mcp-gateway.svg) | An MCP tool call through the team gateway: sealed session, admission, policy, token exchange, upstream call, ledger; inventory refresh and drift holds; reconciler conditions (1.3.0) | Root README; -restapi and -cli docs |
| [orchestration-agent](orchestration-agent.svg) | Each team's orchestration agent, public and private endpoints through afs-edge, and model admission (service ∩ team ∩ agent) | Root README |
| [tenant-isolation](tenant-isolation.svg) | One team's namespace and the eight isolation layers | Root README, adoption guide |
| [budget-enforcement](budget-enforcement.svg) | Reserve, invoke, settle; fail closed; IAM deny; daily CUR reconciliation | Root and -restapi READMEs |
| [desired-state](desired-state.svg) | API transaction, change feed, reconcile loop, status back to clients | Root and -restapi READMEs |
| [identity-access](identity-access.svg) | Human sign-in and roles; agent service accounts, Pod Identity, IAM roles, cross-account links | Root README |
| [work-orders-swarm](work-orders-swarm.svg) | CVE work order to ephemeral swarm to merged PRs and teardown | Root README |
| [repository-map](repository-map.svg) | The five repositories and the contracts between them | Root README, CONTRIBUTING |
| [db-schema-domains](db-schema-domains.svg) | The `afs` schema grouped by domain | -db README |
| [db-roles-rls](db-roles-rls.svg) | Database roles per service and row-level security | -db README |
| [restapi-components](restapi-components.svg) | The four binaries and the clean-architecture layers | -restapi README |
| [restapi-request-pipeline](restapi-request-pipeline.svg) | Middleware and the single-transaction use case | -restapi README |
| [cli-command-pipeline](cli-command-pipeline.svg) | Contract to generated commands; one invocation end to end | -cli README |
| [website-architecture](website-architecture.svg) | Console layers and the generated SDK | -website README |

## Editing a diagram

```bash
# Node 22+, and Playwright for the PNG renders (SVG is written without it)
node docs/diagrams/source/render.mjs                 # every diagram
node docs/diagrams/source/render.mjs tenant-isolation # one diagram
```

- `source/lib.mjs` is the tiny drawing library: `group`, `node`, `edge`, `arrow`, `text`, `step` and `seq`
  (sequence diagrams). Positions are explicit, so layouts stay stable between edits.
- Tones carry meaning: blue for clients, orange for AFS services, green for data, purple for AWS, indigo for
  Kubernetes, red for denials and security.
- Child repositories keep a copy of the SVGs their README shows under `docs/images/`. When you change one of
  those diagrams, copy the new SVG to that repository in the same cycle.
