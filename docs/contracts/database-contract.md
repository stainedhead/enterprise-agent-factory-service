# Database contract: `-db` ↔ `-restapi`

| | |
|---|---|
| **Status** | Contract v1 at schema `000012` (2026-11-21) |
| **Provider** | [enterprise-agent-factory-service-db](https://github.com/stainedhead/enterprise-agent-factory-service-db): migrations, roles, row-level security, `migrate` Go package, `afs-migrate` |
| **Consumer** | [enterprise-agent-factory-service-restapi](https://github.com/stainedhead/enterprise-agent-factory-service-restapi): `afs-api`, `afs-reconciler`, `afs-gateway`, `afs-billing` |
| **Full data dictionary** | `-db/docs/data-model.md` (every table, column rule and function). This document is the interface: who connects how, what each service may touch, and how failures surface |

## 1. Delivery and versioning

| Rule | Detail |
|---|---|
| Module | `github.com/stainedhead/enterprise-agent-factory-service-db` at a semver tag. `-restapi` pins it in `go.mod`; it never vendors SQL or defines tables |
| Migrations | Embedded (`migrations.FS`). `afs-api` runs `migrate.Up` at startup under a PostgreSQL advisory lock; other services check `migrate.Version` and refuse to start if the schema is older than the version they were built against |
| Releases | A new migration is a minor release (`v0.N.0`). A fix to a function or view by a new migration is a patch release. Merged migrations never change; the runner refuses a changed checksum |
| Forward only | Production never runs `down`. Every migration is online-safe and notes its lock impact |
| Compatibility | A release must keep the previous `-restapi` release working (expand, then contract across two releases). Dropping a column used by a released `-restapi` needs that release retired first |
| Engine | PostgreSQL 17 (RDS); nothing newer |
| Bootstrap | `bootstrap/roles.sql` (or `afs-migrate bootstrap-roles`) creates the NOLOGIN roles once per cluster; operators grant them to LOGIN users per service |

## 2. Roles and connections

Each service connects as its own LOGIN user, a member of exactly one role below, with IAM database
authentication on RDS (no static passwords). Pool sizes are per service.

| Role | Service | May | May not |
|---|---|---|---|
| `afs_owner` | `afs-migrate`, `afs-api` at startup (migration step only, separate connection) | DDL | Be used for request traffic |
| `afs_app` | `afs-api` | Read and write desired state; insert audit and outbox; read usage, costs, status, revisions, reports | Write status, spend counters, usage, activity, traffic; update or delete audit |
| `afs_reconciler` | `afs-reconciler` (incl. activity and traffic collectors, outbox publisher, teardown, work order intake and tracking) | Read everything; write `resource_status`, lifecycle `state`, teardown columns, inference profile ARNs, identity and role-link status (agents and pools), `org_aws_accounts`, snapshots, `agent_activity`, `external_traffic`, tag sets; insert work orders from EventBridge, assign them, update repository progress from GitHub, insert work order notifications; purge expired idempotency keys; mark outbox published; create partitions; insert audit (drift) | Change desired state chosen by people |
| `afs_gateway` | `afs-gateway` | Read teams, agents, pools, models, prices, budgets, effective tags; `reserve_spend` / `settle_spend`; insert `usage_events` (stamped with `tag_set_id`), tag sets, threshold events, outbox | Anything else |
| `afs_billing` | `afs-billing` | Read usage, teams, agents, models, prices, budgets, activity, traffic; write `cost_daily`, `cost_reconciliations`, `cost_allocation_tag_status`, tag sets; insert and supersede `model_price_proposals`; read `report_schedules` and `notification_channels` and update a schedule's run columns; insert outbox | Approve prices; change desired state |
| `afs_readonly` | Reporting and support | Read everything except API key hashes and audit before/after payloads | Write |

## 3. Session settings (`afs-api` only)

Every `afs-api` transaction begins with:

```sql
SET LOCAL afs.actor         = '<principal id>';                 -- usr_… or key_…
SET LOCAL afs.service_admin = 'on' | 'off';
SET LOCAL afs.team_ids      = '<comma-separated team ids the caller is bound to>';
SET LOCAL afs.security_operator = 'on' | 'off';                 -- 'on' for security operator people and service-level keys
```

Row-level security uses them: a team-owned row is visible and writable to `afs_app` only when
`afs.caller_sees_team(team_id)` is true. Triggers use `afs.actor` for `created_by`, revisions and price
decisions. `afs.security_operator` lets the caller read and write every work order and its repositories, and
nothing else across teams. A team caller sees a work order when it is assigned to one of its teams or
touches a repository one of its teams owns (`afs.work_order_team`, `afs.caller_owns_work_order_repo`).
A transaction that forgets them sees no team rows (fail closed). Service roles bypass team
scoping by policy (`service_roles_all`) and set `afs.actor = 'system:<service>'`.

## 4. What each service touches

R = read, W = insert/update/delete, I = insert only, U(cols) = update listed columns, F = function.

| Object | api | reconciler | gateway | billing |
|---|---|---|---|---|
| `service_settings`, `models`, `model_prices`, `storage_classes`, `identity_providers`, `service_tags`, `external_systems` (catalog) | W (service admin rows by RLS or trigger) | R | R (models, prices) | R |
| `teams` | W (guardrail columns by trigger, service admins only: ceiling, quotas, `isolation_tier`, `viewer_kubectl`, models flags; `allowed_aws_accounts` when `may_manage_aws_accounts`; `kind` immutable) | R, U(state, deleted_at, torn_down_at, teardown_reason) | R | R |
| `users`, `role_bindings`, `api_keys` (incl. service-level `security_operator` bindings and keys) | W | R | — | — |
| `swarm_stages`, `agent_pools`, `pool_handoffs`, `pool_secret_bindings`, `pool_config_values`, `pool_role_links` | W (ephemeral teams only, by trigger) | R; U(pool role-link status) | R (agent_pools) | R |
| `swarm_templates` | W (service admins) | R | — | — |
| `work_orders` | W (security operators, service admins) | I (EventBridge intake), U(team_id, status, assigned_at, completed_at) | — | — |
| `work_order_repos` | I, U (security operators; assigned team for progress) | I, U(status, pr_url, pr_number, detail, merged_at) | — | — |
| `work_order_notifications` | R | I (once per kind and recipient) | — | — |
| `report_schedules` | W (team-admins; team's own channels only) | — | — | R, U(next_run_at, last_run_at, last_status, last_error) |
| `idempotency_keys` | I, R, D (own principal only, by RLS) | R, D (`purge_idempotency_keys`) | — | — |
| `tag_sets` | R | I, R (`tag_set_for`, `current_team_tag_set`) | I, R | I, R |
| `cost_allocation_tag_status` | R | R | — | W |
| `agents`, `agent_secret_bindings`, `agent_identities`, `agent_role_links`, `agent_config_values`, `namespace_config_values`, `team_models`, `team_tags`, `external_system_optouts`, team `external_systems`, `secrets`, `budgets`, `log_destinations`, `notification_channels`, `work_orders` | W | R; U(status columns) | R (agents, team_models, budgets) | R (agents) |
| `agent_volume_snapshots` | I (manual requests) | W | — | — |
| `org_aws_accounts` | R | W | — | — |
| `spend_counters`, `budget_threshold_events` | R | I, U(limit_usd) | F `reserve_spend`, `settle_spend`; I threshold events | R |
| `usage_events` | R | F `ensure_usage_partition` | I | R |
| `cost_daily` (with `tag_set_id`, `pool_id`), `cost_reconciliations` | R | — | — | W |
| `model_price_proposals` | R, U(status, note) (approve and reject, service admins) | R | — | I, U(status) (supersede) |
| `agent_activity`, `external_traffic` (with `tag_set_id`, `pool_id`, `worker_pod`) | R | W, F `ensure_*_partition` | — | R |
| `resource_status` | R | W | — | — |
| `config_revisions` | R | R | — | — |
| `audit_log` | I | I | — | — |
| `outbox_events` | I | R, U(published_at, attempts) | I | I |
| `export_bundles` | W | R | — | — |

### 4.1 Views the services read

| View | Readers | Purpose |
|---|---|---|
| `agent_config_resolved` | api, reconciler | Effective configuration per agent (ConfigMap content) |
| `agent_external_access` | api, reconciler | Effective external system access per agent (egress policy) |
| `team_effective_tags`, `agent_effective_tags` | api, reconciler, gateway, billing | Tags to apply to resources, pods and Bedrock calls |
| `agent_activity_daily`, `agent_activity_current`, `external_traffic_daily`, `team_budget_position` | api, billing | Reports |
| `cost_daily_by_tag`, `agent_activity_daily_by_tag`, `external_traffic_daily_by_tag` | api, billing | Rollups by the tags in effect when each record happened (`tag_set_id`); a missing required key reads as NULL, shown as *(untagged)* |
| `pool_config_resolved`, `pool_external_access` | api, reconciler | Pool ConfigMap content and egress policy |
| `pool_workers_current` | api | Desired, reporting, working, idle and impaired workers per pool |
| `teams_due_for_teardown` | reconciler | Ephemeral teams whose teardown rule has fired |
| `work_order_progress` | api, reconciler | Counts per repository status and `sla_state` |

All views are `security_invoker`, so RLS applies to `afs_app` callers through them.

### 4.2 Functions

| Function | Caller | Contract |
|---|---|---|
| `afs.secret_path(team_id, agent_id, name)` | api, before `CreateSecret` | Returns the managed Secrets Manager name; the insert trigger recomputes it and rejects a mismatch |
| `afs.reserve_spend(budget_id, period_start, amount) → boolean` | gateway | Atomic. False means reject the call with `BudgetExceeded` |
| `afs.settle_spend(budget_id, period_start, reserved, actual)` | gateway | Releases the reservation and adds the actual cost |
| `afs.account_allowed(team_id, account_id) → boolean` | api, reconciler | Allowed-accounts filter |
| `afs.team_missing_required_tags(team_id, key) → text` | api | Required tags a team still lacks (for clear errors) |
| `afs.ensure_usage_partition`, `afs.ensure_activity_partition`, `afs.ensure_traffic_partition` | reconciler, monthly | Create next month's partitions ahead of time |
| `afs.tag_set_for(team_id, tags) → text`, `afs.current_team_tag_set(team_id) → text` | gateway, reconciler, billing | The snapshot id to stamp on a usage, activity, traffic or cost row; creates the set if new |
| `afs.purge_idempotency_keys() → bigint` | reconciler, every few minutes | Deletes expired keys |
| `afs.caller_sees_team`, `afs.caller_is_service_admin`, `afs.caller_is_security_operator`, `afs.caller_owns_scope`, `afs.work_order_team`, `afs.caller_owns_work_order_repo`, `afs.current_actor` | RLS and triggers | Not called by services directly |

## 5. Transaction rules for `afs-api`

1. One request, one transaction, `READ COMMITTED`, with the session settings of §3.
2. A mutation writes the row, one `audit_log` record (`before`/`after` without secret values) and one
   `outbox_events` record in the same transaction.
3. Updates compare `version` (`UPDATE … WHERE id = $1 AND version = $2`); zero rows → `412` when the
   row exists, `404` otherwise. The `touch_row` trigger bumps `version`.
4. Writes that change desired state bump `generation` where the table has one; the reconciler reports
   `observedGeneration`.
5. Deferred constraint triggers (required tags) fire at commit; the API surfaces them as
   `ValidationError` with the missing keys.
6. Serialization failures (`40001`) and deadlocks (`40P01`) are retried up to 3 times with jitter.

## 6. Error mapping

The database raises named SQLSTATEs; `-restapi/internal/adapter/postgres` maps them, and the HTTP
layer maps those to the [API contract](api-contract.md) §6 codes.

| SQLSTATE | Meaning in this schema | API code |
|---|---|---|
| `23514` check_violation | Field rule, guard trigger (for example a fixed tag, a disabled provider, ceiling exceeded) | `ValidationError` |
| `23502` not_null_violation | Missing required field | `ValidationError` |
| `23505` unique_violation | Duplicate name, slug, issuer, pending proposal | `Conflict` |
| `23503` foreign_key_violation | Unknown reference on write → `ValidationError`; dependents exist on delete → `Conflict` | as stated |
| `55000` object_not_in_prerequisite_state | State does not allow it (provider in use, proposal already decided, key in use by teams) | `Conflict` |
| `42501` insufficient_privilege | Guard trigger refused a role (team caller changing a guardrail, approving a price) | `AccessDenied` |
| `22xxx` data exceptions | Bad value format | `ValidationError` |
| `40001`, `40P01` | Retry (§5.6), then | `InternalError` |
| `P0001` and others | Unexpected | `InternalError` |

Constraint and trigger messages are written for people and may be shown in `message`, but clients
must branch on `code`.

## 7. Known gaps

None at schema `000012`. The gaps listed at `000010` were closed: report schedules, isolation tier and
idempotency keys in `000011`; swarm pools, ephemeral teams and work orders in `000012`. Agent sign-ins
to external systems are not stored (D17): the traffic collector writes them to the team's log delivery.

## 7.1 Idempotency for `afs-api`

1. Before a create, insert `(principal, key, operation, request_sha256, state='in_progress',
   expires_at = now() + api.idempotency_key_ttl_seconds)`. On `23505`, read the row: `completed` with the
   same operation and hash → replay the stored response; different hash or operation → `Conflict`;
   `in_progress` → `Conflict` with `Retry-After`.
2. In the same transaction as the mutation, set `state='completed'`, `response_status` and
   `response_body`. On a 5xx, roll back so the key disappears and a retry runs again.

## 8. Change process

1. Schema change: a `-db` PR with the migration, integration tests (rejected case for every new
   constraint; RLS isolation for every new team table), `docs/data-model.md`, and this contract when §2
   to §6 change. Tag a release after merge.
2. `-restapi` adopts the tag in its own PR (`go get …@vX.Y.Z`), with repository tests against the new
   schema.
3. A breaking change follows expand and contract across two `-db` releases.
