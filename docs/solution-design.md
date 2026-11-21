# Agent Factory Service: Solution Design

Status: Draft for review · 2026-11-20 · Owner: J (Enterprise Architecture) · Requirements: [initial PRD](../enterprise-agent-factory-service-initial-PRD.md)

## 1. Purpose and scope

The Agent Factory Service (AFS) lets enterprise teams create and run their own **software factories**: isolated EKS namespace environments that host containerized teams of AI agents, with human teammates, secrets, identities, budgets and log delivery managed through one control plane. The "Agentic Teammates" project supplies the agent runtime (container images, agent CRDs/manifests). AFS supplies everything around it.

**Deliverables of this product (the software we build):**

| Deliverable | Tech | Notes |
|---|---|---|
| Control plane REST API | Go 1.27 | System of record API, RBAC enforced here |
| Reconciler (management plane automation) | Go 1.27 | Applies desired state from RDS to EKS/AWS, continuously |
| LLM gateway | Go 1.27 | Bedrock proxy that meters tokens and enforces hard caps |
| Billing ingestor | Go 1.27 | Daily CUR reconciliation and EKS split cost attribution |
| `afs` CLI | Go 1.27 | AWS CLI design conventions (own repo) |
| `@afs/sdk` accelerator SDK | TypeScript 7 | Typed wrapper over the REST API |
| Web management console | TypeScript 7, React | Clean architecture, consumes `@afs/sdk` |
| Datastore | RDS PostgreSQL 17 | Desired state, audit, usage ledger |
| Documentation | Markdown | This set, plus runbooks and OpenAPI |

**Toolchain confirmed on 2026-11-20:** Go 1.27.4 (latest 1.27 patch on proxy.golang.org) and TypeScript 7.0.2 (npm `typescript@latest`, the native Go-based compiler).

### 1.1 Phases

| Phase | Capability | Design hooks we build now |
|---|---|---|
| 1 | Long-running teams for development and maintenance | Full build |
| 2 | Short-term "swarm rentals" for one job with a hard cost cap | `team.kind = ephemeral`, `expires_at`, budget `period = lifetime`, auto-teardown, `work_orders` |
| 3 | CVE remediation teams | `work_orders` (kind `cve_remediation`, SLA due date), event outbox to EventBridge, notification channels |

## 2. Requirements analysis

### 2.1 Functional requirements

| ID | Requirement | Source |
|---|---|---|
| F1 | Create, update, suspend, resume and delete teams. Each team maps to one isolated EKS namespace | J |
| F2 | Define the agents in a team (template/image, persona, model, resources, secrets, schedule). One agent is one pod | J |
| F3 | Manage human teammates and their role on the team | J |
| F4 | Manage agent identities (Kubernetes service account, AWS IAM role via Pod Identity, external identities such as a GitHub App installation) | J |
| F5 | Manage secrets as references to AWS Secrets Manager. Values are write-only through the API and never stored in or returned by AFS | J |
| F6 | Budgets per team with alert thresholds and a hard cap enforced in near real time | J |
| F7 | Budget and usage reporting: real time from the gateway, reconciled daily against CUR, including EKS compute | J |
| F8 | Log delivery configuration per team (CloudWatch, S3, OTLP, Splunk/Datadog via HEC/API) | J |
| F9 | Team configuration (allowed models, egress allow-list, resource quotas) and non-secret configuration values at namespace and agent level | J |
| F10 | Three roles: service admin, team-admin, team viewer. Enforced in API, respected by CLI and web | J |
| F11 | Desired state stored in RDS PostgreSQL, versioned and audited. Exportable as a portable bundle and importable in another account or cluster | J |
| F12 | Reconciler applies stored state on startup and continuously, recovering from failure and reverting manual drift | J |
| F13 | Web console, CLI and SDK over one REST API | J |
| F14 | (Phase 2/3) Ephemeral teams, work orders, event hooks and notifications | J |

### 2.2 Non-functional requirements

| Area | Requirement |
|---|---|
| Isolation | A team's agents cannot reach another team's pods, secrets, IAM permissions, logs or budget. Namespace + NetworkPolicy is the primary network boundary |
| Security | SSO via enterprise IdP (OIDC). Least privilege everywhere. No long-lived AWS keys. Secrets never in the DB or in logs |
| Auditability | Every mutation recorded with actor, time, request id and before/after. Append-only |
| Availability | API and gateway multi-AZ, 99.9%. Gateway outage must fail closed for spend (no unmetered calls) |
| Recoverability | RDS PITR (35 days) + cross-region snapshot copy. Full environment rebuild from DB in under 1 hour |
| Portability | Export bundle is versioned, checksummed, and holds no secret values |
| Cost | Spend enforcement lag under 1 request (pre-authorized reservation). Reporting freshness: real time (gateway), daily (CUR) |
| Scale (initial) | 200 teams, 2,000 agents, 500 RPS on the gateway |

### 2.3 Assumptions and open questions

1. **IdP:** OIDC-compliant enterprise IdP (Entra ID or Okta). Groups claim available for role mapping. *Confirm which.*
2. **Cluster topology:** one shared EKS cluster per environment (dev/stage/prod) to start. The design allows a `cluster_id` per team later.
3. **Network policy engine:** VPC CNI native network policy, or Cilium if FQDN egress rules are wanted. *Recommend Cilium for FQDN egress (GitHub, Jira, package registries).*
4. **Agentic Teammates contract:** assumed to expose a Kubernetes CRD (e.g. `AgentTeam`/`Agent`) or Helm chart. The reconciler renders whichever it exposes. *Confirm the interface.*
5. **Currency:** USD only.

## 3. Architecture overview

```
                    ┌──────────────── Enterprise IdP (OIDC) ────────────────┐
                    │                                                        │
  Browser ── Web console (TS7/React) ──┐                                     │
  Terminal ── afs CLI (Go) ────────────┼──► ALB ──► afs-api (Go) ◄── JWT ────┘
  Pipelines ── @afs/sdk (TS7) ─────────┘              │  RBAC, validation, audit
                                                      ▼
                                       ┌────── RDS PostgreSQL ──────┐
                                       │ desired state · audit ·    │
                                       │ usage ledger · outbox      │
                                       └───┬──────────┬─────────┬───┘
                     LISTEN/NOTIFY + poll  │          │         │ outbox
                                           ▼          │         ▼
                          afs-reconciler (Go, leader) │    EventBridge ──► notifications
                            │  K8s API   │ AWS APIs   │                  (Slack/email/Jira/webhook)
                            ▼            ▼            │
        ┌──── EKS cluster ─────────────────────┐   IAM, Pod Identity, Secrets Manager,
        │ ns afs-t-payments  ns afs-t-search … │   Bedrock app inference profiles,
        │  agents (Agentic Teammates runtime)  │   CloudWatch/S3 log destinations
        │    │ projected SA token              │
        │    ▼                                 │
        │ ns afs-system: afs-llm-gateway ──────┼──► Bedrock (via VPC endpoint)
        └──────────────────────────────────────┘        │ per-team inference profile
                                                         ▼
          afs-billing-ingestor ◄── CUR 2.0 (S3/Athena) ── daily reconciliation
```

### 3.1 Components

**afs-api (Go).** Stateless REST service behind an internal ALB. Validates OIDC JWTs, resolves the caller's role bindings, authorizes every request, writes desired state and an audit record in one transaction, and emits an outbox event. Never calls Kubernetes or AWS for mutating desired state; that is the reconciler's job. It does call Secrets Manager directly for write-only secret value operations so values never touch the DB.

**afs-reconciler (Go).** Single active replica via Kubernetes Lease leader election (two replicas for HA). On startup it performs a full reconcile of every resource; afterwards it reacts to `LISTEN afs_changes` notifications and runs a periodic full resync (default 10 minutes) to catch drift. For each team it converges:

- Namespace `afs-t-<slug>` with labels `afs.io/team-id`, Pod Security Admission `restricted`.
- `ResourceQuota`, `LimitRange`.
- `NetworkPolicy` default deny all ingress/egress, then allow DNS, allow egress to `afs-llm-gateway`, allow egress to the team's egress allow-list (FQDN rules with Cilium, or via an egress proxy).
- ServiceAccounts per agent, EKS Pod Identity associations to the team's IAM role.
- One StatefulSet with exactly one replica per agent (stable name, ServiceAccount and IAM session). There is no replica count: a team scales by adding agents.
- One ConfigMap per agent (`agent-<name>-config`) holding its resolved configuration values (`afs.agent_config_resolved`), loaded with `envFrom` and mounted read-only at `/etc/afs/config` (one file per name). A change to a namespace value re-renders every ConfigMap that links to it and rolls those agents (a pod-template hash annotation), because environment variables only change on restart. A ConfigMap edited by hand is restored.
- One persistent volume per agent from the StatefulSet's `volumeClaimTemplate` (EBS CSI, encrypted, `WaitForFirstConsumer`, tagged `afs-team-id` and `afs-agent-id`), mounted at `/var/lib/agent`. The StatefulSet's PVC retention policy is `Retain` for both scale-down and delete, so pausing or re-creating the StatefulSet never loses data; the reconciler alone deletes a volume, following the agent's on-delete rule. Snapshots are EBS snapshots through CSI `VolumeSnapshot`, taken on the agent's schedule, pruned to its retention count, and recorded in `agent_volume_snapshots`. The team's `ResourceQuota` includes `requests.storage`.
- IAM role `afs-team-<id>` with an ABAC policy scoped by `aws:PrincipalTag/afs-team-id`, and a permissions boundary `afs-team-<id>-boundary` that allows `sts:AssumeRole` and `sts:TagSession` only on `arn:aws:iam::<account>:role/*` for the organization accounts matching the team's allowed-accounts filter. The boundary is re-rendered when the filter or the organization account list changes.
- A dedicated IAM role `afs/agents/<namespace>/<agent>` for each agent whose `iam_identity` is `dedicated`, with the team's boundary attached and its own Pod Identity association. For each of the agent's cross-account links, an inline statement grants `sts:AssumeRole` and `sts:TagSession` on that exact role ARN. A Secret-free AWS config file (`agent-<name>-aws`) is mounted at `/etc/afs/aws/config` with `AWS_CONFIG_FILE` set, holding one profile per link (`role_arn`, `external_id`, `credential_source = EcsContainer`, `duration_seconds`), so the agent runs `aws --profile <name>` or the SDK equivalent.
- The AWS Organizations account list, mirrored hourly into `org_aws_accounts` (id, name, status). Each link is verified by assuming its role with the agent's identity on creation, daily and on demand; the result (`pending_trust`, `verified`, `failed`) is written to `agent_role_links`. Links whose account falls outside the filter or is suspended are set to `disabled` and removed from the agent's grants and profile file.
- Bedrock application inference profile per (team, model) with cost allocation tags.
- ExternalSecret (External Secrets Operator) objects that project referenced Secrets Manager entries into the namespace.
- Agent workloads rendered from the Agentic Teammates CRD/Helm chart.
- Log delivery (Fluent Bit output per team or CloudWatch subscription filters).

It records `observed_generation`, phase and conditions per resource in `resource_status`, which the API and UI display. Drift (live state differs from desired) is corrected and logged as an audit event with actor `system:reconciler`. Deletes use an ordered finalizer flow: scale agents to zero, apply each agent's on-delete rule to its volume (final snapshot, then delete or retain), revoke IAM, delete inference profiles, delete namespace, mark row `deleted`.

Volume drift is handled like any other: a volume smaller than desired is expanded (online, EBS supports it); a PVC that is missing is re-created from the agent's latest completed snapshot when one exists (empty otherwise) and raises an alert; a volume bigger than desired, or of another storage class, is reported as a condition rather than changed, because EBS cannot shrink and a class change needs a data migration. EBS volumes live in one Availability Zone, so an agent reschedules within its volume's zone; moving it to another zone is a restore from snapshot.

**afs-llm-gateway (Go).** The only path from agents to Bedrock. Runs in `afs-system`, multi-AZ.

1. Agent calls the gateway with its projected service account token (audience `afs-gateway`).
2. Gateway validates the token with the Kubernetes TokenReview API (cached), which yields namespace and service account, hence `team_id` and `agent_id`.
3. Gateway checks the model is allowed for the team, then **reserves** the worst-case cost (`max_tokens` × output price + input tokens × input price) against the team's active budget with an atomic `UPDATE … WHERE spent + reserved + :est <= cap RETURNING`. If the reservation fails the request is rejected with `429 BudgetExceeded`.
4. Gateway assumes the team's Bedrock role (`afs-team-<id>-bedrock`) with session tags and invokes the team's application inference profile.
5. On response it settles the reservation to the actual token cost and writes a `usage_events` row (batched).

Agents' own Pod Identity role has **no** `bedrock:*` permissions, so the gateway cannot be bypassed. When a hard cap is reached, the reconciler also attaches an explicit-deny inline policy to the team's Bedrock role (the IAM kill switch), so even a gateway bug cannot overspend. The deny is removed on budget reset or increase.

At higher scale the spend counters move to ElastiCache (Redis/Valkey) with Postgres as the durable ledger; the interface is designed for that swap.

**afs-billing-ingestor (Go).** Daily job. Reads CUR 2.0 (with EKS split cost allocation enabled) via Athena, attributes Bedrock cost by the `afs-team-id` cost allocation tag on inference profiles and EKS compute by namespace, writes `cost_daily` and `cost_reconciliations` (gateway estimate vs. billed actual, variance). Variance over a threshold (default 3%) raises an alert to service admins and can adjust the model price catalog.

**Event outbox and notifications.** Every mutation writes an `outbox_events` row in the same transaction. A publisher (inside the reconciler process) sends them to an EventBridge bus `afs-events` with at-least-once delivery. Rules route to Slack, email (SES), Jira or team webhooks configured in `notification_channels`. This is the hook for phase 3 CVE workflows (e.g. `work_order.pr_opened` notifies the owning team).

## 4. Multi-tenancy and isolation

| Layer | Control |
|---|---|
| Network | Namespace per team. Default-deny `NetworkPolicy` for ingress and egress. Only DNS, gateway and explicit egress allow-list. No cross-namespace traffic. Admission policy (Kyverno or ValidatingAdmissionPolicy) blocks teams from creating their own NetworkPolicies, Services of type LoadBalancer/NodePort, or hostNetwork pods |
| Compute | Pod Security Admission `restricted`. ResourceQuota/LimitRange. Optional dedicated Karpenter NodePool per sensitivity tier (taints + tolerations) for teams needing node-level isolation |
| Kubernetes API | Agents' service accounts get no Kubernetes RBAC by default (`automountServiceAccountToken: false` except the projected gateway token). Humans have no kubectl access by default; team viewers can optionally get read-only via EKS access entries scoped to their namespace |
| AWS IAM | One IAM role per team, ABAC by `afs-team-id` tag. Secrets, S3 prefixes, log groups and inference profiles are all tagged with the team id, and the policy only matches its own tag |
| Secrets | Secrets Manager name set by AFS, never by users: `<service>/<namespace>/<agent-name>/<secret-name>` or `<service>/<namespace>/_shared/<secret-name>` (§6). IAM uses prefix rules on that path, with tag `afs-team-id` as a second check. KMS key per environment with an encryption context of team id |
| Data (AFS DB) | Every team-scoped table has `team_id`. API authorization filters on it. PostgreSQL row-level security as defense in depth (`app.allowed_team_ids` session setting) |
| Spend | Separate inference profile, budget, counters and IAM deny per team |
| Logs | Separate log group / S3 prefix / destination per team |

Namespace isolation shares the kernel. That is acceptable for internal enterprise tenants; the dedicated-NodePool option exists for teams that handle regulated data, and gVisor/Kata can be added later as a runtime class.

## 5. Identity and access

### 5.1 Human identity

OIDC Authorization Code + PKCE for the web console; OIDC device authorization grant for the CLI (`afs sso login`); short-lived API keys (hashed in DB, max 90 days, scoped to one team and role) for pipelines. The API validates JWTs against the IdP's JWKS and maps `sub` to a `users` row (just-in-time provisioning on first login).

### 5.2 Roles

| Role | Scope | Summary |
|---|---|---|
| `service_admin` | Global | Everything, including service settings, model catalog and pricing, creating/deleting teams, all teams' data, export/import, audit |
| `team_admin` | One team | Manage that team's agents, members, budgets (within the limit a service admin set), identities, secrets, configuration, log delivery, notification channels |
| `team_viewer` | One team | Read that team's configuration, status, usage and audit. Secrets show name, description and reference metadata, never values |

Role bindings can be granted to a user or to an IdP group (`subject_type = group`, matched on the `groups` claim), so enterprises manage membership in the IdP. A person can hold different roles on different teams. Budget **ceilings** (`max_budget_usd`) are set by service admins; team admins set budgets up to that ceiling.

### 5.3 Permission matrix

| Action | service_admin | team_admin | team_viewer |
|---|:-:|:-:|:-:|
| Create / delete team | ✓ | | |
| Update team settings, quotas, egress | ✓ | ✓ | |
| Suspend / resume team | ✓ | ✓ | |
| View team, status, events | ✓ | ✓ | ✓ |
| Create / update / delete agents, scale, restart | ✓ | ✓ | |
| View agents | ✓ | ✓ | ✓ |
| Add / remove members, change roles | ✓ | ✓ (cannot grant service_admin) | |
| View members | ✓ | ✓ | ✓ |
| Create / rotate / delete secrets, bind to agents | ✓ | ✓ | |
| View secret metadata (never values) | ✓ | ✓ | ✓ |
| Manage agent identities | ✓ | ✓ | |
| Set a team's allowed AWS accounts | ✓ | | |
| Add / remove / verify agent cross-account role links | ✓ | ✓ | |
| View allowed accounts, role links, trust policies | ✓ | ✓ | ✓ |
| Set budget (≤ ceiling), thresholds | ✓ | ✓ | |
| Set budget ceiling | ✓ | | |
| View usage, cost, reconciliation | ✓ | ✓ | ✓ |
| Manage log destinations, notification channels | ✓ | ✓ | |
| Issue team API keys | ✓ | ✓ | |
| View audit log (team) | ✓ | ✓ | ✓ |
| Service settings, model catalog, pricing | ✓ | | |
| Export / import bundles | ✓ | | |

Each action is a named permission (e.g. `agents:write`, `secrets:read-metadata`). The API's route table declares the permission for each route; one authorization function `Authorize(principal, permission, teamID)` is the only place decisions are made. `GET /v1/me` returns the caller's bindings and effective permissions per team so the CLI and web can hide or disable actions. **The client-side check is UX only; the API is the enforcement point.**

### 5.4 Agent identity

Each agent gets a Kubernetes ServiceAccount `agent-<name>` in its team namespace. Identities are modeled explicitly in `agent_identities`:

- `k8s_service_account` (always), used for gateway authentication.
- `aws_iam_role` via EKS Pod Identity. Default: the shared team role (`agents.iam_identity = 'team_shared'`). Option: a dedicated role `afs/agents/<namespace>/<agent>` (`'dedicated'`), with the team's permissions boundary, for least privilege and for cross-account access.
- Cross-account role links (`agent_role_links`, dedicated agents only): a target role ARN in another organization account, a profile name, a maximum session and an AFS-generated external ID. The account must match the team's allowed-accounts filter (`teams.allowed_aws_accounts`, glob patterns over account ids and names; `*` for every account), which service admins set. The filter is enforced three times: in the API, in the database (`afs.account_allowed`, by trigger) and in IAM (the team's permissions boundary). AFS shows the target account owner this trust policy:

  ```json
  {
    "Effect": "Allow",
    "Principal": { "AWS": "arn:aws:iam::<afs-account>:role/afs/agents/<namespace>/<agent>" },
    "Action": ["sts:AssumeRole", "sts:TagSession"],
    "Condition": { "StringEquals": { "sts:ExternalId": "<external-id>", "aws:PrincipalTag/afs-team-id": "<team-id>" } }
  }
  ```

  Glob patterns, not regular expressions, because IAM policies match ARNs with wildcards only, so the same pattern can be checked in SQL and rendered into the boundary.
- Phase 2 swarm pools can use a shared named role: one role name deployed to one or many organization accounts (typically by a CloudFormation StackSet) that trusts the pool's role, with one profile per account. The same filter applies.
- `github_app` installation or other external identity (e.g. a bot account in Jira), credentials held as a referenced secret.

Agent actions in AWS carry session tags `afs-team-id`, `afs-agent-id`, so CloudTrail attributes every call to an agent.

## 6. Secrets management

- AFS stores **references only**: ARN, version stage, rotation settings, description. Never the value.
- **One creation mode.** The API takes a scope (team-shared or one agent), a name, a description and the value. It creates the secret in Secrets Manager under the managed path, writes the value (`CreateSecret` / `PutSecretValue`), discards it, and stores the ARN. Registering an arbitrary existing ARN is not supported, because it would bypass the hierarchy.
- **Managed hierarchy.** The Secrets Manager name is always `<service>/<namespace>/<agent-name>/<secret-name>`, or `<service>/<namespace>/_shared/<secret-name>` for team-shared secrets. `<service>` is the installation prefix (service setting `secrets.path_prefix`, default `afs`), and `<namespace>` is `afs-t-<slug>`. The database computes the path (`afs.secret_path`) and rejects an ARN that does not match it. Team slug, agent name and secret name are immutable, so a path never changes. `_shared` cannot collide with an agent name, because agent names start with a letter.
- **Access by prefix.** `afs-api` may create and write values only under `<service>/*`. The team's External Secrets store reads `<service>/<namespace>/*`. A per-agent IAM role (AGT-6) reads `<service>/<namespace>/<agent-name>/*` and `<service>/<namespace>/_shared/*`. No human role reads values.
- Values are write-only. There is no read-value endpoint. The API returns `lastChangedAt`, `versionId` and rotation status.
- Bindings (`agent_secret_bindings`) say which agent receives which secret as an env var or file. A team-shared secret can be bound to any agent of the team; an agent secret only to its own agent (enforced in the database). The reconciler renders ExternalSecret objects; External Secrets Operator syncs them using the team's IAM role, so a team's ESO access is limited by ABAC to its own secrets.
- Rotation: Secrets Manager rotation Lambdas where applicable; ESO refresh interval 1h; a rotate action triggers a rolling restart of bound agents.

## 7. Budgets and cost

### 7.1 Model

- `budgets`: per team; `period` = `monthly` | `lifetime` (ephemeral teams); `amount_usd`; `thresholds` (default 50/80/100); `on_exhaust` = `block` | `notify`; optional `expires_at`.
- `model_prices`: price per 1M input/output tokens per Bedrock model, effective-dated, maintained by service admins (seeded from the AWS price list).
- `spend_counters`: one row per budget period: `spent_usd`, `reserved_usd`. Hot path for the gateway.
- `usage_events`: append-only ledger, partitioned by month.
- `cost_daily`: daily rollup by team/agent/model and source (`gateway` estimate, `cur` billed, `eks_compute`).

### 7.2 Enforcement path (near real time)

Reserve → invoke → settle, as in section 3.1. Thresholds emit `budget.threshold_crossed` events once per period per threshold. At 100% with `block`, the gateway rejects calls and the reconciler applies the IAM deny. Agents receive a structured error and the Agentic Teammates runtime can pause gracefully.

### 7.3 Reporting

- Real-time view: from `spend_counters` and `usage_events` (seconds).
- Daily reconciled view: from CUR via the ingestor, including EKS compute (split cost allocation by namespace) and any non-gateway spend.
- Showback/chargeback export by cost center (CSV via API).

## 8. Desired state, versioning and portability

- Every desired-state row has `version` (optimistic concurrency, exposed as `ETag`/`If-Match`) and `generation` (incremented on spec change). The reconciler writes back `observed_generation`.
- `config_revisions`: a trigger snapshots every change to versioned tables (who, when, full JSON), giving history and rollback ("restore revision N").
- `audit_log`: append-only (UPDATE/DELETE revoked from the app role and blocked by trigger).
- **Backups:** RDS automated backups with PITR, daily snapshot copied cross-region and cross-account (AWS Backup vault with vault lock).
- **Export bundle:** `POST /v1/exports` produces a versioned, SHA-256-checksummed JSON (or YAML) document with `schemaVersion`, all teams, agents (including volume settings and configuration values), namespace configuration values, agent IAM identity and cross-account links with their external IDs, each team's allowed-accounts filter, members, bindings, budgets, configuration, secret *references* and each agent's latest volume *snapshot reference*. Import can restore volumes from those snapshots once they are shared with or copied to the target account and region. Stored in S3 and downloadable.
- **Import:** `POST /v1/imports` with a mapping file (old account id → new, ARN rewrites, cluster id), dry-run by default, showing a plan (create/update/skip) before apply. Secrets must already exist (replicated via Secrets Manager multi-region replication or recreated) in the target account.
- **Restart behavior:** the reconciler's startup full-reconcile re-applies everything. A brand-new cluster plus a restored DB converges to the full environment with no manual steps.

## 9. Ephemeral teams and work orders (phase 2/3 hooks)

- `teams.kind = ephemeral`, `expires_at`, lifetime budget. The reconciler tears down on expiry, on budget exhaustion (if configured), or when all work orders complete.
- `work_orders`: `kind` (`general`, `cve_remediation`), `external_ref` (e.g. `CVE-2026-12345`), `target_repos`, `sla_due_at`, `status`, `results` (PR URLs). Created by the security team via API or an EventBridge integration.
- A CVE flow: security system → `POST /v1/work-orders` → AFS creates or reuses an ephemeral remediation team with a cap → agents open PRs → `work_order.pr_opened` events → notification to the owning team's channel, tracked against the SLA.

## 10. REST API design

Base path `/v1`. JSON. Resource-oriented. camelCase fields. All IDs are prefixed ULIDs-as-text (`team_01J…`, `agt_01J…`) for readability in CLI output.

**Conventions**

- Pagination: `?maxResults=50&nextToken=…` → `{ "items": [...], "nextToken": "…" }` (AWS style, maps directly onto CLI `--max-items`/`--starting-token`).
- Concurrency: `ETag` on GET, `If-Match` required on PUT/PATCH/DELETE.
- Idempotency: `Idempotency-Key` header on POST.
- Errors: `{ "code": "AccessDenied", "message": "...", "requestId": "..." }` with codes `ValidationError`, `NotFound`, `Conflict`, `PreconditionFailed`, `AccessDenied`, `Unauthenticated`, `BudgetExceeded`, `Throttled`, `InternalError`.
- `X-Request-Id` on every response, stored in audit records.
- Async status: mutating calls return `202`-style semantics in the body (`status.phase = Pending`) and the client polls or watches `status`.

**Resources**

```
GET    /v1/me                                         caller, bindings, effective permissions
GET    /v1/teams                       POST /v1/teams
GET    /v1/teams/{teamId}              PATCH, DELETE
POST   /v1/teams/{teamId}:suspend      POST /v1/teams/{teamId}:resume
GET    /v1/teams/{teamId}/status                      reconcile status + conditions
GET    /v1/teams/{teamId}/members      POST           role bindings for users/groups
PATCH/DELETE /v1/teams/{teamId}/members/{bindingId}
GET    /v1/teams/{teamId}/agents       POST
GET/PATCH/DELETE /v1/teams/{teamId}/agents/{agentId}
POST   /v1/teams/{teamId}/agents/{agentId}:restart    POST …:scale
GET    /v1/teams/{teamId}/identities   POST, GET/DELETE /{identityId}
GET    /v1/teams/{teamId}/secrets      POST create {scope, agentId?, name, description, value}; path is server-set
GET/PATCH/DELETE /v1/teams/{teamId}/secrets/{secretId}
PUT    /v1/teams/{teamId}/secrets/{secretId}/value    write-only, 204
POST   /v1/teams/{teamId}/secrets/{secretId}:rotate
GET/PUT /v1/teams/{teamId}/budget
GET    /v1/teams/{teamId}/usage?from&to&groupBy=agent|model|day
GET    /v1/teams/{teamId}/costs?from&to               reconciled daily costs
GET    /v1/teams/{teamId}/log-destinations   POST, PATCH, DELETE
GET    /v1/teams/{teamId}/notification-channels   POST, PATCH, DELETE
GET    /v1/teams/{teamId}/api-keys     POST, DELETE
GET    /v1/teams/{teamId}/audit-events
GET    /v1/teams/{teamId}/revisions    POST /v1/teams/{teamId}/revisions/{rev}:restore
GET    /v1/work-orders                 POST, GET/PATCH /{id}           (phase 2/3)
GET    /v1/models                      (all roles: enabled models)
GET/PUT /v1/admin/settings             service_admin
GET/POST/PATCH /v1/admin/models, /v1/admin/model-prices    service_admin
GET    /v1/admin/audit-events          service_admin
POST   /v1/exports   GET /v1/exports/{id}   POST /v1/imports (dryRun)   service_admin
GET    /healthz  /readyz  /metrics
```

The OpenAPI 3.1 document (`api/openapi.yaml`) is the contract. The TypeScript SDK types are generated from it and wrapped by hand-written ergonomic clients; the Go server uses it for request validation tests.

## 11. CLI design (`afs`)

Follows AWS CLI conventions.

```
afs <service> <operation> [--parameters] [global options]

afs configure                       # interactive; writes ~/.afs/config
afs configure sso                   # OIDC issuer, client id
afs sso login --profile prod
afs teams list-teams --output table
afs teams create-team --name payments --display-name "Payments Factory" --cost-center CC1234
afs teams describe-team --team-id team_01J...
afs agents list-agents --team-id team_01J... --query "items[?status.phase=='Running'].name"
afs agents create-agent --team-id ... --cli-input-json file://agent.json
afs agents create-agent --generate-cli-skeleton
afs secrets create-secret --team-id ... --name github-token --secret-string file://token.txt
afs budgets put-budget --team-id ... --amount-usd 5000 --period monthly --thresholds 50 80 100
afs usage get-usage --team-id ... --from 2026-11-01 --group-by model
afs members add-member --team-id ... --user-email dev@corp.example --role team_viewer
afs admin export-config --output-file bundle.json
```

- **Services:** `configure`, `sso`, `teams`, `agents`, `members`, `identities`, `secrets`, `budgets`, `usage`, `logs`, `notifications`, `api-keys`, `audit`, `work-orders`, `models`, `admin`.
- **Operation verbs:** `list-*`, `describe-*`/`get-*`, `create-*`, `update-*`, `delete-*`, `put-*` (replace), plus actions (`suspend-team`, `restart-agent`, `rotate-secret`).
- **Global options:** `--profile`, `--endpoint-url`, `--output json|table|text|yaml`, `--query` (JMESPath), `--no-paginate`, `--max-items`, `--page-size`, `--starting-token`, `--cli-input-json`, `--generate-cli-skeleton`, `--debug`, `--no-cli-pager`, `--color`.
- **Config files:** `~/.afs/config` (profiles: endpoint, sso issuer, default team, output) and `~/.afs/credentials` / SSO token cache under `~/.afs/sso/cache`. Env vars: `AFS_PROFILE`, `AFS_ENDPOINT_URL`, `AFS_API_KEY`, `AFS_DEFAULT_OUTPUT`.
- **Paging:** auto-paginates by default like the AWS CLI; prints `NextToken` when `--max-items` truncates.
- **Errors:** `An error occurred (AccessDenied) when calling the CreateAgent operation: ...`, exit code 254 for service errors, 252 for usage errors, 255 for others (AWS CLI codes).
- **RBAC:** the CLI calls `GET /v1/me` (cached 5 minutes) only to give helpful messages; the API's 403 is authoritative.

## 12. Web console architecture (TypeScript 7)

Clean architecture with the dependency rule pointing inward. See `02-ui-design.md` for screens.

```
web/src/
  domain/          entities, value objects, policies (pure TS, no imports from outer layers)
    team.ts  agent.ts  budget.ts  permission.ts  money.ts
  application/     use cases + ports (interfaces the outer layers implement)
    ports/ TeamRepository.ts  AgentRepository.ts  SessionPort.ts ...
    usecases/ ListTeams.ts  CreateAgent.ts  SetBudget.ts  GetCurrentPrincipal.ts ...
  infrastructure/  adapters implementing ports with @afs/sdk, OIDC PKCE auth, storage
    sdk/ SdkTeamRepository.ts ...   auth/ OidcSession.ts
  presentation/    React components, routes, view models, hooks (depends on application)
    routes/  components/  viewmodels/  hooks/
  main/            composition root: wires adapters into use cases, provides via context
```

- Stack: React 19, React Router, TanStack Query (caching in presentation, not in domain), Vite for bundling, `tsc` 7 for type-checking (`--noEmit`), Vitest for unit tests of domain and use cases, Playwright for e2e.
- Permission checks live in `domain/permission.ts` (`can(principal, "agents:write", teamId)`) and are used by view models to hide or disable controls. The API remains authoritative; a 403 surfaces as an "access denied" banner.
- No secret value is ever held in client state beyond the input field during a create/rotate submit.

## 13. Repository layout

Docs-only wrapper root plus four independent child repositories (same pattern as `stainedhead/agentic-teams`):

```
enterprise-agent-factory-service/              docs-only root: PRD, this design, UI mockups, cross-repo specs
  enterprise-agent-factory-service-db/         SQL + Go module (git-ignored by the root)
    migrations/        NNNNNN_name.{up,down}.sql, embedded (go:embed)
    bootstrap/roles.sql
    migrate/           migration runner used by afs-api and afs-migrate
    cmd/afs-migrate/
  enterprise-agent-factory-service-restapi/    Go 1.27
    api/openapi.yaml   REST contract
    cmd/afs-api  cmd/afs-reconciler  cmd/afs-gateway  cmd/afs-billing
    internal/domain  internal/usecase  internal/authz  internal/adapter/{httpapi,postgres,k8s,aws}
    deploy/helm/  deploy/terraform/
  enterprise-agent-factory-service-cli/        Go 1.27
    cmd/afs  internal/cli  (client generated from the OpenAPI contract)
  enterprise-agent-factory-service-website/    TypeScript 7 pnpm workspace
    packages/sdk/      @afs/sdk
    apps/console/      web management console (clean architecture)
```

## 14. Observability and operations

- OpenTelemetry traces and metrics from all Go services; Prometheus `/metrics`.
- Key SLIs: API p99 latency, reconcile lag (`now - updated_at` for un-observed generations), drift corrections per hour, gateway reservation failures, gateway added latency, CUR variance.
- Runbooks: restore from PITR, rebuild a cluster from DB, rotate KMS key, revoke a team (emergency IAM deny), import bundle into a new account.

## 15. Key decisions and alternatives considered

| Decision | Chosen | Alternative | Why |
|---|---|---|---|
| Source of truth | PostgreSQL + reconciler | CRDs in etcd (pure operator) | Portability across clusters, SQL reporting, audit, backups independent of cluster |
| Spend enforcement | Gateway reservation + IAM deny backstop | AWS Budgets actions | Budgets lag hours; reservations are per request |
| Agent → Bedrock auth | Projected SA token to gateway; gateway assumes team role | Agents call Bedrock directly | Direct calls cannot be metered or capped in real time |
| Secrets | Secrets Manager refs + ESO | Store encrypted values in DB | Keeps AFS out of the secret blast radius |
| CLI language | Go | Python (like AWS CLI) | Single static binary, shares API types |
| Network policy | Cilium (recommended) | VPC CNI network policy | FQDN egress rules for SaaS endpoints |
| Cross-account access | Dedicated agent role + role links with external IDs, inside a per-team glob filter | Shared team role trusted by every target account | Least privilege per agent, CloudTrail attribution in the target account, and a guardrail central teams control |
