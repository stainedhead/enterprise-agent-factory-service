# Database contract: `-db` ↔ `-restapi`

| | |
|---|---|
| **Status** | Contract v1 at schema 000017 (2026-11-21). 000013 implements root PRD decisions D30, D31, D33 to D36 and D45; some D35 rules landed in 000011 and 000012, as marked below. 000014 implements D54 (agent template catalog) and D49 (export and import transport). 000015 closes the gaps that proving the `-db` PRD revealed; 000016 adds the service access paths `-restapi` requested (X-DB-1 to X-DB-6). 000017 adds `afs.schema_version()` for the startup check of services that cannot read the tracking table. Planned first release containing 000011 to 000017: `v0.13.0` |
| **Provider** | [enterprise-agent-factory-service-db](https://github.com/stainedhead/enterprise-agent-factory-service-db): migrations, roles, row-level security, `migrate` Go package, `afs-migrate` |
| **Consumer** | [enterprise-agent-factory-service-restapi](https://github.com/stainedhead/enterprise-agent-factory-service-restapi): `afs-api`, `afs-reconciler`, `afs-gateway`, `afs-billing` |
| **Full data dictionary** | `-db/docs/data-model.md` (every table, column rule and function). This document is the interface: who connects how, what each service may touch, and how failures surface |

## 1. Delivery and versioning

| Rule | Detail |
|---|---|
| Module | `github.com/stainedhead/enterprise-agent-factory-service-db` at a semver tag. `-restapi` pins it in `go.mod`; it never vendors SQL or defines tables |
| Migrations | Embedded (`migrations.FS`). `afs-api` runs `migrate.Up` at startup under a PostgreSQL advisory lock; other services call `afs.schema_version()` (000017: `SECURITY DEFINER`, returns the highest applied version, executable by every service role, because the service roles cannot read `public.afs_schema_migrations`) and refuse to start if the schema is older than the version they were built against. `migrate.Up` and `migrate.Down` take options: `migrate.WithLockTimeout(d)` sets `lock_timeout` in each migration transaction (default `migrate.DefaultLockTimeout`, 10 s; 0 disables; negative is `migrate.ErrNegativeLockTimeout`), so a migration blocked on a table lock fails with `55P03` instead of queueing traffic behind it; `afs-migrate --lock-timeout` is the same |
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
| `afs_app` | `afs-api` | Read and write desired state; insert audit and outbox; read usage, costs, status, revisions, reports; before the caller's scope is known, `authenticate_api_key`, `resolve_workload` and `team_directory` (000016) | Write status, spend counters, usage, activity, traffic; update or delete audit |
| `afs_reconciler` | `afs-reconciler` (incl. activity and traffic collectors, outbox publisher, teardown, work order intake and tracking) | Read everything except idempotent response bodies and API key hashes; `LISTEN afs_desired_state`; open spend periods (`ensure_spend_counter`), release expired reservations, clear expired ceiling overrides and lower budgets to the base ceiling, drop partitions older than 13 months; write `resource_status`, lifecycle `state`, teardown columns, inference profile ARNs, identity and role-link status (agents and pools), `org_aws_accounts`, snapshots, `agent_activity`, `external_traffic`, tag sets; insert work orders from EventBridge, assign them and create their remediation teams (`instantiate_work_order_team`, 000016), mark pools deleted (000016), update repository progress from GitHub, insert work order notifications; purge expired idempotency keys; mark outbox published; create partitions; insert audit (drift) | Change desired state chosen by people |
| `afs_gateway` | `afs-gateway` | Read teams, agents, pools, models (incl. `max_output_tokens`), prices, budgets, effective tags; `ensure_spend_counter`, `reserve_spend_held` / `settle_reservation` (and the older `reserve_spend` / `settle_spend`); insert `usage_events` (stamped with `tag_set_id`), tag sets, threshold events, outbox; `resolve_workload` (000016) | Anything else |
| `afs_billing` | `afs-billing` | Read usage, teams, agents, models, prices, budgets, activity, traffic; write `cost_daily`, `cost_reconciliations`, `cost_allocation_tag_status`, tag sets; insert and supersede `model_price_proposals`; read `report_schedules` and `notification_channels` and update a schedule's run columns; insert outbox | Approve prices; change desired state |
| `afs_readonly` | Reporting and support | Read everything except API key hashes and audit before/after payloads | Write |

## 3. Session settings (`afs-api` only)

Every `afs-api` transaction begins with:

```sql
SET LOCAL afs.actor         = '<principal id>';                 -- usr_…, key_…, or the agt_… / pool_… id of a workload principal
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
| `service_settings`, `models` (incl. `max_output_tokens`, 000013), `model_prices`, `storage_classes`, `identity_providers`, `service_tags`, `external_systems` (catalog) | R all; W service admins only (`app_write` policies on `service_settings`, `models`, `model_prices`, `storage_classes` from 000013; the others by RLS or trigger) | R | R (models, prices) | R |
| `teams` | W. Guard trigger (000013 extends it to every column listed): service admins only for `max_budget_usd`, `ceiling_override_usd`, `ceiling_override_expires_at`, `quotas`, `isolation_tier`, `viewer_kubectl`, `may_add_external_systems`, `may_manage_aws_accounts`; `allowed_aws_accounts` also by team-admins when `may_manage_aws_accounts`; `max_budget_usd` may not go below the current budget amount; `kind` immutable (`23514`, 000012) | R, U(state, deleted_at, torn_down_at, teardown_reason, ceiling_override_usd, ceiling_override_expires_at: clear only) | R | R |
| `team_models` | R; W service admins only (000013) | R | R | R |
| `users` | R; W own row only, or service admins (000013) | R | — | — |
| `role_bindings` | W: service-level roles (`service_admin`, `security_operator`) only by service admins; team roles only for teams the caller sees (000013) | R | — | — |
| `api_keys` (incl. service-level `security_operator` keys) | W; lookup by hash before scope through F `authenticate_api_key` (000016). `created_at` is set by the database on insert and cannot change (`55000`, 000015) | R (not `key_hash`) | — | — |
| `swarm_stages`, `agent_pools`, `pool_handoffs`, `pool_secret_bindings`, `pool_config_values`, `pool_role_links` | W (ephemeral teams only, by trigger) | R; U(pool role-link status); U(`agent_pools.state`, `deleted_at`) (000016); remediation teams' rows through F `instantiate_work_order_team` (000016) | R (agent_pools) | R |
| `swarm_templates` | W (service admins) | R | — | — |
| `agent_templates` (000014: `id` `tpl_…`, `name`, `description`, `harness`, `default_resources`, `allowed_image_digests`, `current_image_digest`, `enabled`) | R all; W service admins only (`app_write` policy: `42501` on insert, zero rows on update and delete for others). The API lists only enabled templates to teams. Delete of a template in use → `23503` (`Conflict`: disable it instead) | R (flags existing agents and pools with `TemplateRetired`) | — | — |
| `work_orders` | W security operators and service admins; team callers R only; D security operators and service admins (000012) | I (EventBridge intake), U(team_id, status, assigned_at, completed_at); F `instantiate_work_order_team` creates the team and assigns the order (000016) | — | — |
| `work_order_repos` | I, U security operators and service admins; the assigned team may U only its repositories' progress columns (`work_order_repo_progress_guard`, `42501`, 000012); D security operators and service admins | I, U(status, pr_url, pr_number, detail, merged_at) | — | — |
| `work_order_notifications` | R | I (once per kind and recipient) | — | — |
| `report_schedules` | W (team-admins; team's own channels only) | — | — | R, U(next_run_at, last_run_at, last_status, last_error) |
| `idempotency_keys` | I, R, D (own principal only, by RLS). A CHECK (000011) refuses a `response_body` containing a `secretKey` field anywhere; the API stores those responses with `secretKey` removed (D35, D52) | R(principal, key, expires_at) only (column grant, 000011), D (`purge_idempotency_keys`) | — | — |
| `tag_sets` | R | I, R (`tag_set_for`, `current_team_tag_set`) | I, R | I, R |
| `cost_allocation_tag_status` | R | R | — | W |
| `agents` and `agent_pools` (000014: nullable `template_id` → `agent_templates`) | `template_id` set: a new row, or a changed `template_id` or `image`, needs an enabled template and an image digest on its allowed list, else `23514` (`agents_template_guard`, `agent_pools_template_guard`); NULL `template_id` is not guarded and the free-text `template` stays | as the rows below | as the rows below | as the rows below |
| `agents`, `agent_secret_bindings`, `agent_identities`, `agent_role_links`, `agent_config_values`, `namespace_config_values`, `team_tags`, `external_system_optouts`, team `external_systems`, `secrets`, `budgets`, `log_destinations`, `notification_channels` | W | R; U(status columns) | R (agents, team_models, budgets) | R (agents) |
| `agent_volume_snapshots` | I (manual requests) | W | — | — |
| `org_aws_accounts` | R | W | — | — |
| `budgets` | W (`on_exhaust = 'notify'` only by service admins and only on persistent teams, guard 000013) | U(amount_usd) only to lower it to the base ceiling when an override expires | R | R |
| `spend_counters`, `budget_threshold_events` | R | F `ensure_spend_counter` (period start), U(limit_usd) | F `ensure_spend_counter`, `reserve_spend_held`, `settle_reservation` (and `reserve_spend`, `settle_spend`); I threshold events | R |
| `spend_reservations` (000013: `id` uuid, `budget_id`, `period_start`, `amount_usd`, `holder`, `expires_at`) | — | F `release_expired_reservations` (every minute) | through the functions only | — |
| `usage_events` | R | F `ensure_usage_partition`, `drop_partitions_older_than` | I | R |
| `cost_daily` (with `tag_set_id`, `pool_id`), `cost_reconciliations` | R | — | — | W. `cost_reconciliations.status` is derived by trigger from the amounts and `billing.variance_alert_pct` (the written value is replaced); amounts below 0 are `23514` (000015) |
| `model_price_proposals` | R, U(status, note) (approve and reject, service admins) | R | — | I, U(status) (supersede) |
| `agent_activity`, `external_traffic` (with `tag_set_id`, `pool_id`, `worker_pod`) | R | W, F `ensure_activity_partition`, `ensure_traffic_partition`, `drop_partitions_older_than` | — | R |
| `resource_status` | R | W | — | — |
| `config_revisions` | R | R | — | — |
| `audit_log` | I within the caller's teams, and any team or none when `actor_id = afs.current_actor()` (policy `app_own_audit`, 000016: denials on service routes and on teams the caller does not see). Reads stay team-scoped, so no `INSERT … RETURNING` for such rows | I | — | — |
| `outbox_events` | I within the caller's teams; with `afs.security_operator` on, `work_order.*` events on `work_orders` for any team or none (policy `app_operator_work_order_events`, 000016); no `INSERT … RETURNING` for such rows | R, U(published_at, attempts) | I | I |
| `export_bundles` (000014: nullable `s3_uri` and `sha256`, `download_url`, `download_expires_at`, `size_bytes`) | W (export request rows in `pending`, with no `s3_uri` or `sha256` yet; import rows with the applied report, no `s3_uri`, with the `sha256` of the body) | R, U(status, summary, finished_at, s3_uri, sha256, download_url, download_expires_at, size_bytes) for exports (column grant, 000014); no insert or delete | — | — |
| Desired-state tables (every table with `generation`) | Writes fire `afs.notify_desired_state()` (000013) | `LISTEN afs_desired_state`; payload `'<table>:<team_id>:<id>'` (empty team part for service-level tables, e.g. `agent_templates::tpl_…`, 000014); also polls `generation <> observed_generation` every 30 s; full resync every 10 min (D30) | — | — |

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
| `teams_due_for_teardown` | reconciler | Ephemeral teams whose teardown rule has fired; only those (000015: before, every active ephemeral team was listed, with a NULL reason when none was due) |
| `work_order_progress` | api, reconciler | Counts per repository status and `sla_state` |

All views are `security_invoker`, so RLS applies to `afs_app` callers through them.

### 4.2 Functions

| Function | Caller | Contract |
|---|---|---|
| `afs.secret_path(team_id, agent_id, name)` | api, before `CreateSecret` (team and agent scope) | Returns the managed Secrets Manager name; the insert trigger recomputes it and rejects a mismatch |
| `afs.secret_path(team_id, agent_id, pool_id, name)` (000012) | api, before `CreateSecret` (all scopes) | Same, and for a pool secret returns `<prefix>/<namespace>/<pool>/<name>`; with `pool_id` NULL it equals the 3-argument form |
| `afs.ensure_spend_counter(budget_id, period_start) → numeric` (000013) | gateway before reserving; reconciler at period start | Idempotent; creates the period's counter with the limit from the budget and returns the limit. The reconciler emits `budget.reset` when it opens a period |
| `afs.reserve_spend_held(budget_id, period_start, amount, holder) → uuid` (000013) | gateway | Atomic. `holder` is the calling pod. Returns a reservation id, or NULL, meaning reject with `402 BudgetExceeded`. The reservation expires after `gateway.reservation_ttl_seconds` (default 900) |
| `afs.settle_reservation(id uuid, budget_id, period_start, actual) → boolean` (000013) | gateway, always with the budget and period it reserved against | On a live hold: releases it, adds the actual cost, returns true. On a hold already released (expired or settled): returns false and still adds the actual cost, so a call that runs past the TTL still counts. A budget or period that does not match the hold raises `22023` |
| `afs.release_expired_reservations() → bigint` (000013) | reconciler, every minute | Releases expired reservations; returns the count (alerted when above zero for 3 runs) |
| `afs.reserve_spend(budget_id, period_start, amount) → boolean`, `afs.settle_spend(budget_id, period_start, reserved, actual)` | gateway (compatibility) | Older pair without expiry; kept so a released gateway keeps working, removed in a later expand/contract cycle |
| `afs.drop_partitions_older_than(months) → SETOF text` (000013, returns the dropped partition names) | reconciler, monthly with `13` | Detaches and drops partitions of `usage_events`, `agent_activity` and `external_traffic` older than the given months (D36). Never touches `audit_log` |
| `afs.image_digests_ok(text[]) → boolean`, `afs.template_use_guard()` (000014) | `agent_templates` check; agents and pools trigger | Digest list shape; refuses a new agent or pool on a disabled template or a digest not on the allowed list (`23514`) | 
| `afs.resolve_repo_owners(host, repo) → SETOF text` (000014, SECURITY DEFINER) | api before `CreateWorkOrder`, for repositories given without an owner; reconciler | Team ids whose namespace configuration value `AFS_OWNED_REPOS` lists the repository (entries split on commas or whitespace, case-insensitive), only at the best match (exact `host/owner/repo` over `host/owner/*`), skipping teams that are deleting or deleted. Returns ids only, because a security operator cannot read other teams' configuration through RLS. Zero rows → the API's `unownedRepos`; two or more → `ambiguousRepos` (D38) |
| `afs.authenticate_api_key(key_sha256 bytea) → (key_id, team_id, principal, role, roles, expires_at, revoked_at, state, team_state)` (000016, SECURITY DEFINER, `afs_app` only) | api, for every `afsk_` key, before the caller's scope is known | No row for an unknown hash. `team_id` NULL for a service-level key; `principal` is the key id (the audit `actor_id`); `state` `active`, `expired` or `revoked`; `team_state` the team's state (NULL for a service key). The API answers `401` unless `state = 'active'` and the team, if any, is active. Sets `last_used_at` at most once a minute for a usable key. Never returns the hash |
| `afs.resolve_workload(namespace, service_account) → (team_id, agent_id, pool_id)` (000016, SECURITY DEFINER, `afs_app` and `afs_gateway`) | api and gateway, for a workload token | ServiceAccount `agent-<name>` or `pool-<name>` in an active team's namespace → that team and the live agent or pool; no row otherwise (unknown name, other namespace, team not active, workload deleted) |
| `afs.team_directory() → (id, slug, display_name)` (000016, SECURITY DEFINER, `afs_app` only) | api, `ListTeamDirectory` | Every team not deleted, by slug, when `afs.service_admin` or `afs.security_operator` is on; otherwise `42501` |
| `afs.instantiate_work_order_team(work_order_id) → text` (000016, SECURITY DEFINER, `afs_reconciler` only) | reconciler, for each open work order with a template (RC-12) | Locks the work order and returns its team if it has one (idempotent; concurrent calls create one team). Otherwise creates, in the caller's transaction, an ephemeral team (`slug` `wo-<ulid>`, `teardown_rule` and expiry `now() + ttl_hours` from the template, `costCenter` and `ownerEmail` from the template spec or settings `work_orders.cost_center` / `work_orders.owner_email`, ceiling equal to the budget), `spec.tags`, a lifetime blocking budget (`work_orders.budget_usd`, else the template's), `team_models` for the pools' models, `spec.stages`, `spec.pools` (stage by name), `spec.handoffs` (`from`/`to` pool names) and `spec.configValues` (`pool`, `name`, `value`, `source` default literal); sets `team_id`, `status = 'assigned'`, `assigned_at`; writes audit `InstantiateWorkOrderTeam` and outbox `team.created`, `pool.created` per pool, `work_order.assigned`; triggers write revisions and change notifications. Template `secrets` are not created (see §7). Unknown work order `P0002`; not open, no or disabled template, no cost center or owner `55000`; unknown model or stage `23503`; other rules as for any team (`23514`) |
| `afs.account_allowed(team_id, account_id) → boolean` | api, reconciler | Allowed-accounts filter |
| `afs.team_missing_required_tags(team_id, key) → text` | api | Required tags a team still lacks (for clear errors) |
| `afs.ensure_usage_partition`, `afs.ensure_activity_partition`, `afs.ensure_traffic_partition` | reconciler, monthly | Create next month's partitions ahead of time |
| `afs.tag_set_for(team_id, tags) → text`, `afs.current_team_tag_set(team_id) → text` | gateway, reconciler, billing | The snapshot id to stamp on a usage, activity, traffic or cost row; creates the set if new |
| `afs.purge_idempotency_keys() → bigint` | reconciler, every few minutes | Deletes expired keys |
| `afs.caller_sees_team`, `afs.caller_is_service_admin`, `afs.caller_is_security_operator`, `afs.caller_owns_scope`, `afs.work_order_team`, `afs.caller_owns_work_order_repo`, `afs.current_actor`, `afs.new_id` (000016, owner only) | RLS, triggers and other functions | Not called by services directly |

| `afs.schema_version() → bigint` (000017, SECURITY DEFINER, `afs_app`, `afs_reconciler`, `afs_gateway`, `afs_billing`, `afs_readonly`) | every service, at startup | The highest applied migration version, or 0 when none; nothing else is exposed. A service refuses to start when it is lower than the version the service was built against |

## 5. Transaction rules for `afs-api`

1. One request, one transaction, `READ COMMITTED`, with the session settings of §3.
2. A mutation writes the row, one `audit_log` record (`before`/`after` without secret values) and, when
   the mutation has an event type in the [API contract](api-contract.md) §7, one `outbox_events` record in
   the same transaction. A mutation with no event type writes no outbox row (API contract CD-7).
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
| `23514` check_violation | Field rule, guard trigger (for example a fixed tag, a disabled provider, ceiling exceeded, a `kind` change, `notify` on an ephemeral team, a disabled agent template or an image digest not on the template's allowed list, a succeeded export without `s3_uri`, an image without a full `@sha256:<64 hex>` digest (000015), a secret on a service-level notification channel (000015), a negative reconciliation amount (000015)) | `ValidationError` |
| `23502` not_null_violation | Missing required field | `ValidationError` |
| `23505` unique_violation | Duplicate name, slug, issuer, pending proposal | `Conflict` |
| `23503` foreign_key_violation | Unknown reference on write → `ValidationError`; dependents exist on delete → `Conflict` | as stated |
| `55000` object_not_in_prerequisite_state | State does not allow it (provider in use, proposal already decided, key in use by teams, a change to `api_keys.created_at` (000015); for the reconciler, a work order that cannot be instantiated (000016)) | `Conflict` |
| `P0002` no_data_found | `instantiate_work_order_team` on an unknown work order (reconciler only) | logged, not shown |
| `55P03` lock_not_available | A migration hit `lock_timeout` (`migrate`); retry the deployment when traffic is lower | startup fails |
| `42501` insufficient_privilege | Guard trigger or policy refused a role (team caller changing a guardrail, approving a price, `team_directory` without service admin or security operator, an audit row for another actor, a non-work-order outbox event outside the caller's teams) | `AccessDenied` |
| `22xxx` data exceptions | Bad value format; `22023` from `settle_reservation` is a gateway bug and is logged, not shown to agents | `ValidationError` |
| `40001`, `40P01` | Retry (§5.6), then | `InternalError` |
| `P0001` and others | Unexpected | `InternalError` |

Constraint and trigger messages are written for people and may be shown in `message`, but clients
must branch on `code`.

## 7. Known gaps

The gaps listed at `000010` were closed: report schedules, isolation tier and idempotency keys in
`000011`; swarm pools, ephemeral teams and work orders in `000012`. Agent sign-ins to external systems
are not stored (D17): the traffic collector writes them to the team's log delivery.

The review gaps at `000012` (unguarded ceilings and quotas, writable service catalogs, `role_bindings`
and work order writes, secret keys in idempotent responses, no change notification, no spend period
rollover, no reservation expiry, no retention, missing settings, missing `models.max_output_tokens`) are
closed by `000011`, `000012` and `000013` as marked above. The two gaps left open at `000013` are closed
by `000014`: the agent template catalog (`agent_templates`, `template_id` on agents and pools, root PRD
AGT-11, D54) and the export and import transport (`export_bundles` with nullable `s3_uri` and `sha256`,
`download_url`, `download_expires_at`, `size_bytes`; D49). `000015` closes the gaps found while proving
the `-db` PRD (service-level channels hold no secret, `teams_due_for_teardown` lists only teams due, derived
reconciliation status, database-set API key creation time, full image digests) and `000016` the access gaps
`-restapi` found (X-DB-1 to X-DB-6: API key and workload lookups, team directory, remediation team creation,
pool deletion, audit and outbox inserts outside the caller's teams). Still open after `000016`:

- `audit_log` partitioning (OQ-4).
- Swarm template `secrets`: `instantiate_work_order_team` does not create them, because a secret row needs
  the ARN Secrets Manager assigns and `afs_reconciler` may not insert `secrets` or `pool_secret_bindings`.
  A follow-up is needed before a template that declares secrets can be instantiated with them.

Two things the API must know about `000014`: the free-text `template` columns of `agents` and `agent_pools`
stay and are not checked against the catalog (only rows with `template_id` are guarded), and the database
checks the shape of `harness` (kebab-case), not a closed list, because the harnesses belong to Agentic
Teammates.

## 7.0 Service settings

The same list as root PRD §6.13. The database refuses a value outside its range.

| Key | Default | Allowed values | Migration |
|---|---|---|---|
| `secrets.path_prefix` | `"afs"` | `^[a-z][a-z0-9-]{0,30}$` | 000003 |
| `pricing.price_list_sync` | `true` | boolean | 000010 |
| `billing.variance_alert_pct` | `5` | 0 to 100 | 000010 |
| `api.idempotency_key_ttl_seconds` | `3600` | 60 to 604800 | 000011 |
| `teams.ephemeral_max_days` | `90` | 1 to 365 | 000012 |
| `work_orders.sla_warning_hours` | `48` | 1 to 720 | 000012 |
| `billing.tag_activation_acknowledged` | `false` | boolean | 000012 |
| `work_orders.notification_channel_id` | `null` | null or a service-level email channel id | 000012 |
| `reports.idle_cpu_millicores` | `50` | 1 to 4000 | 000013 |
| `egress.denied_spike_threshold` | `20` | 1 to 100000 (per agent or pool, 5 minutes) | 000013 |
| `gateway.reservation_ttl_seconds` | `900` | 60 to 3600 | 000013 |
| `api.cors_origins` | `[]` | JSON array of `https://host[:port]` origins | 000013 |
| `work_orders.cost_center` | unset | string of 1 to 100 characters; cost center of a remediation team whose template names none | 000016 |
| `work_orders.owner_email` | unset | string `local@domain`; owner of a remediation team whose template names none | 000016 |

## 7.1 Idempotency for `afs-api`

1. Before a create, insert `(principal, key, operation, request_sha256, state='in_progress',
   expires_at = now() + api.idempotency_key_ttl_seconds)`. On `23505`, read the row: `completed` with the
   same operation and hash → replay the stored response; different hash or operation → `Conflict`;
   `in_progress` → `Conflict` with `Retry-After`.
2. In the same transaction as the mutation, set `state='completed'`, `response_status` and
   `response_body`. On a 5xx, roll back so the key disappears and a retry runs again.
3. A response that contains `secretKey` (`CreateApiKey`, `CreateServiceApiKey`) is never stored as is:
   the API stores the body with `secretKey` removed, and the CHECK of 000011 refuses any body that still
   contains it. A replay returns the stored body, so the secret is shown only once (D52).

## 8. Change process

1. Schema change: a `-db` PR with the migration, integration tests (rejected case for every new
   constraint; RLS isolation for every new team table), `docs/data-model.md`, and this contract when §2
   to §6 change. Tag a release after merge.
2. `-restapi` adopts the tag in its own PR (`go get …@vX.Y.Z`), with repository tests against the new
   schema.
3. A breaking change follows expand and contract across two `-db` releases.
