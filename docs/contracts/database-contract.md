# Database contract: `-db` ↔ `-restapi`

| | |
|---|---|
| **Status** | Contract v1 at schema 000019 (2026-11-22), with migration 000020 (Paperclip team collaboration, [paperclip-team-collaboration-PRD.md](../../paperclip-team-collaboration-PRD.md) DB-US-44 to DB-US-47) specified in §7.2 and not yet built; it is the next minor release after 000019. 000013 implements root PRD decisions D30, D31, D33 to D36 and D45; some D35 rules landed in 000011 and 000012, as marked below. 000014 implements D54 (agent template catalog) and D49 (export and import transport). 000015 closes the gaps that proving the `-db` PRD revealed; 000016 adds the service access paths `-restapi` requested (X-DB-1 to X-DB-6). 000017 adds `afs.schema_version()` for the startup check of services that cannot read the tracking table, and `identity_providers.cli_client_id` (the CLI public client, D48; `client_id` is the console client). Planned first release containing 000011 to 000017: `v0.13.0` 000018 adds daily report rollups and the follow-ups `-restapi` asked for (X-DB-8 to X-DB-10, `agent_secret_bindings` triggers, ETag-stable report schedules); 000019 adds `afs.record_work_order_secret` (template secrets for remediation teams) and `afs.event_detail`, and gives the outbox payloads written by `afs.instantiate_work_order_team` the API contract §7 envelope. Schema 000019 is at `-db` `main` (83f0345) and is not yet tagged; `-restapi` pins its pseudo-version until the tag exists |
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

Each service connects as its own LOGIN user, a member of exactly one role below (000020 adds `afs_edge`; run `afs-migrate bootstrap-roles` before deploying a release that contains it), with IAM database
authentication on RDS (no static passwords). Pool sizes are per service.

| Role | Service | May | May not |
|---|---|---|---|
| `afs_owner` | `afs-migrate`, `afs-api` at startup (migration step only, separate connection) | DDL | Be used for request traffic |
| `afs_app` | `afs-api` | Read and write desired state; insert audit and outbox; read usage, costs, status, revisions, reports; before the caller's scope is known, `authenticate_api_key`, `resolve_workload` and `team_directory` (000016) | Write status, spend counters, usage, activity, traffic; update or delete audit |
| `afs_reconciler` | `afs-reconciler` (incl. activity and traffic collectors, outbox publisher, teardown, work order intake and tracking) | Read everything except idempotent response bodies and API key hashes; `LISTEN afs_desired_state`; open spend periods (`ensure_spend_counter`), release expired reservations, clear expired ceiling overrides and lower budgets to the base ceiling, drop partitions older than 13 months; write `resource_status`, lifecycle `state`, teardown columns, inference profile ARNs, identity and role-link status (agents and pools), `org_aws_accounts`, snapshots, `agent_activity`, `external_traffic`, tag sets; insert work orders from EventBridge, assign them and create their remediation teams (`instantiate_work_order_team`, 000016) and record the secrets of their template (`record_work_order_secret`, 000019), run the report rollups (`rollup_reports_recent`, `rollup_reports_daily`, 000018), mark pools deleted (000016), update repository progress from GitHub, insert work order notifications; purge expired idempotency keys; mark outbox published; create partitions; insert audit (drift) | Change desired state chosen by people |
| `afs_gateway` | `afs-gateway` | Read teams, agents, pools, models (incl. `max_output_tokens`), prices, budgets, effective tags; `ensure_spend_counter`, `reserve_spend_held` / `settle_reservation` (and the older `reserve_spend` / `settle_spend`); insert `usage_events` (stamped with `tag_set_id`), tag sets, threshold events, outbox; `resolve_workload` (000016) | Anything else |
| `afs_billing` | `afs-billing` | Read usage, teams, agents, models, prices, budgets, activity, traffic; write `cost_daily`, `cost_reconciliations`, `cost_allocation_tag_status`, tag sets; insert and supersede `model_price_proposals`; (000018) read `service_settings (key, value)` and `team_models (team_id, model_id, inference_profile_arn)` and the daily rollups; read `report_schedules` and `notification_channels` and update a schedule's run columns; insert outbox | Approve prices; change desired state |
| `afs_edge` (000020) | `afs-edge` | `EXECUTE` on the `afs.collab_*` and `afs.record_collab_access` / `afs.emit_collab_secret_detected` functions of §7.2 and `afs.schema_version()`; `LISTEN afs_desired_state` | Any table privilege, any other function |
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
| `report_schedules` | W (team-admins; team's own channels only) | — | — | R, U(next_run_at, last_run_at, last_status, last_error); an update of only those four columns leaves `version` and `updated_at` alone, so client ETags survive a run (000018) |
| `idempotency_keys` | I, R, D (own principal only, by RLS). A CHECK (000011) refuses a `response_body` containing a `secretKey` field anywhere; the API stores those responses with `secretKey` removed (D35, D52) | R(principal, key, expires_at) only (column grant, 000011), D (`purge_idempotency_keys`) | — | — |
| `tag_sets` | R | I, R (`tag_set_for`, `current_team_tag_set`) | I, R | I, R |
| `cost_allocation_tag_status` | R | R | — | W |
| `agents` and `agent_pools` (000014: nullable `template_id` → `agent_templates`) | `template_id` set: a new row, or a changed `template_id` or `image`, needs an enabled template and an image digest on its allowed list, else `23514` (`agents_template_guard`, `agent_pools_template_guard`); NULL `template_id` is not guarded and the free-text `template` stays | as the rows below | as the rows below | as the rows below |
| `agents`, `agent_secret_bindings`, `agent_identities`, `agent_role_links`, `agent_config_values`, `namespace_config_values`, `team_tags`, `external_system_optouts`, team `external_systems`, `secrets`, `budgets`, `log_destinations`, `notification_channels` | W | R; U(status columns) | R (agents, team_models, budgets) | R (agents) |
| `team_collaboration`, `agent_collaboration` (000020, §7.2) | W (`team_collaboration`: insert with a collaboration agent, U(`web_ui_enabled`, `rest_api_enabled`, `registration_mode`); `agent_collaboration`: insert and U(`connect`, `paperclip_agent_id`); the latter only while `registration_mode = 'manual'`) | R; `agent_collaboration` U(`paperclip_agent_id`, `link_state`, `last_synced_at`, `last_error`); resource status in `resource_status` | — | — |
| `collaboration_access` (000020, partitioned) | R (RLS: own teams) | R, F `ensure_collaboration_access_partition`, `drop_partitions_older_than` | — | — |
| `collab_hostname_holds` (000020) | R | R, D (expired rows) | — | — |
| `secrets` rows with `managed_by = 'paperclip'` (000020) | R | I, U, D (only such rows; trigger `42501` for any other secret row) | — | — |
| `agent_volume_snapshots` | I (manual requests) | W | — | — |
| `org_aws_accounts` | R | W | — | — |
| `budgets` | W (`on_exhaust = 'notify'` only by service admins and only on persistent teams, guard 000013) | U(amount_usd) only to lower it to the base ceiling when an override expires | R | R |
| `spend_counters`, `budget_threshold_events` | R | F `ensure_spend_counter` (period start), U(limit_usd) | F `ensure_spend_counter`, `reserve_spend_held`, `settle_reservation` (and `reserve_spend`, `settle_spend`); I threshold events | R |
| `spend_reservations` (000013: `id` uuid, `budget_id`, `period_start`, `amount_usd`, `holder`, `expires_at`) | — | F `release_expired_reservations` (every minute) | through the functions only | — |
| `usage_events` | R | F `ensure_usage_partition`, `drop_partitions_older_than` | I | R |
| `cost_daily` (with `tag_set_id`, `pool_id`), `cost_reconciliations` | R | — | — | W. `cost_reconciliations.status` is derived by trigger from the amounts and `billing.variance_alert_pct` (the written value is replaced); amounts below 0 are `23514` (000015) |
| `model_price_proposals` | R, U(status, note) (approve and reject, service admins) | R | — | I, U(status) (supersede) |
| `agent_activity`, `external_traffic` (with `tag_set_id`, `pool_id`, `worker_pod`) | R | W, F `ensure_activity_partition`, `ensure_traffic_partition`, `drop_partitions_older_than` | — | R |
| `agent_activity_rollup_daily`, `external_traffic_rollup_daily` (000018; day, team, agent or pool, tag set) | R (RLS: own teams) | R, F `rollup_reports_recent`, `rollup_reports_daily` (the only writers) | — | R |
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
| `agent_activity_rollup_daily`, `external_traffic_rollup_daily` (tables, 000018) | api, reconciler, billing | Daily-range activity and traffic reports, service-wide and 90-day ones included. Sum rows to the level a report shows; utilization is working ÷ (working + idle) over the sums; `workers` is per group, so take the maximum across tag sets; `requests` and `errors` stay NULL where no proxy saw HTTP |
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
| `afs.instantiate_work_order_team(work_order_id) → text` (000016, SECURITY DEFINER, `afs_reconciler` only) | reconciler, for each open work order with a template (RC-12) | Locks the work order and returns its team if it has one (idempotent; concurrent calls create one team). Otherwise creates, in the caller's transaction, an ephemeral team (`slug` `wo-<ulid>`, `teardown_rule` and expiry `now() + ttl_hours` from the template, `costCenter` and `ownerEmail` from the template spec or settings `work_orders.cost_center` / `work_orders.owner_email`, ceiling equal to the budget), `spec.tags`, a lifetime blocking budget (`work_orders.budget_usd`, else the template's), `team_models` for the pools' models, `spec.stages`, `spec.pools` (stage by name), `spec.handoffs` (`from`/`to` pool names) and `spec.configValues` (`pool`, `name`, `value`, `source` default literal); sets `team_id`, `status = 'assigned'`, `assigned_at`; writes audit `InstantiateWorkOrderTeam` and outbox `team.created`, `pool.created` per pool, `work_order.assigned`; triggers write revisions and change notifications. Template `secrets` are not created here; the reconciler records them afterwards with `afs.record_work_order_secret`; its team, pool and work order events carry the `afs.event_detail` envelope (000019). Unknown work order `P0002`; not open, no or disabled template, no cost center or owner `55000`; unknown model or stage `23503`; other rules as for any team (`23514`) |
| `afs.rollup_reports_daily(from, to) → bigint` (000018, SECURITY DEFINER, `afs_reconciler` only) | reconciler | Recomputes `agent_activity_rollup_daily` and `external_traffic_rollup_daily` for the UTC days `from`..`to` (at most 121 days, else `22023`): deletes those days and inserts them again in one transaction under an advisory lock, so it is idempotent and readers see the old rows until commit. Returns the rows written. Also the backfill after a database restore |
| `afs.rollup_reports_recent(days default 2) → bigint` (000018, `afs_reconciler` only) | reconciler | `rollup_reports_daily` for the last `days` UTC days including today (1 to 121). The reconciler runs it with 2 every 5 to 15 minutes and with 7 nightly for late samples |
| `afs.touch_row_runner_exempt()` (000018, trigger `report_schedules_touch`) | report schedules | Like `touch_row()`, but an update that changes only `last_run_at`, `last_status`, `last_error` and `next_run_at` leaves `version` and `updated_at` alone. A mixed update, or one that changes nothing, bumps as before; revision and change-feed triggers still fire |
| `afs.record_work_order_secret(work_order_id, pool_id, name, description, arn, delivery, target) → text` (000019, SECURITY DEFINER, `afs_reconciler` only; `afs_app` gets `42501`) | reconciler (RC-12), after `instantiate_work_order_team`, once per `spec.secrets` entry of the template | Records one template secret for a work order whose status is `assigned`, `in_progress` or `pr_opened` and that has a team, on one `enabled` or `paused`, not deleted pool of that team: a managed `secrets` row (`pool_id` set), its `pool_secret_bindings` row (`delivery` `env` or `file`; `target` an environment variable name or an absolute path; `description` NULL is stored as an empty string), audit `RecordWorkOrderSecret` (`actor_type` `system`, `actor_id` `afs.current_actor()`, `pool_id` set, no value) and outbox `secret.created` with the envelope (`data` `{secretId, name, scope: pool}`, `poolId` in the envelope). Returns the secret id (`sec_…`). The ARN must be `arn:aws:secretsmanager:<region>:111122223333:secret:<path>-<6 alphanumeric>` with `<path>` equal to `afs.secret_path(team, NULL, pool, name)`, so the reconciler creates the empty secret at that path first and passes the ARN Secrets Manager returned. Idempotent on (team, name): an existing secret returns its id and writes nothing, whatever ARN or pool is passed. Never stores a value. Errors: unknown work order `P0002`; no team or work order not live `55000`; pool unknown, of another team or not live `23503`; bad ARN, delivery or target `23514`; target already bound on the pool or ARN already used `23505` |
| `afs.event_detail(team_id, pool_id, data) → jsonb` (000019, owner only) | `instantiate_work_order_team`, `record_work_order_secret` | Builds the outbox payload of API contract §7: `{id (evt_ + ULID), occurredAt (UTC, `YYYY-MM-DDTHH:MM:SSZ`), teamId, poolId?, actor (afs.current_actor()), data}` |
| `afs.collab_routes() → (team_id, slug, namespace, hostname, team_state, agent_id, agent_state, web_ui_enabled, rest_api_enabled, web_ui_effective, rest_api_effective, may_expose, ready, not_ready_reason, service_name, port, provider_id, issuer_url, groups_claim, collab_client_id, collab_client_secret_arn)` (000020, SECURITY DEFINER, `afs_edge` only) | afs-edge, at start, on `LISTEN afs_desired_state` and every 30 s | The route table; see §7.2 for the column rules |
| `afs.collab_settings() → (key, value)` (000020, `afs_edge` only) | afs-edge | The seven `collab.*` settings and nothing else |
| `afs.collab_principal(team_id, subject, provider_id, groups text[]) → (binding_id, role, subject_type, user_id)` (000020, `afs_edge` only) | afs-edge, per decision (cached 60 s) | Role bindings that apply to a signed-in person on a team; §7.2 |
| `afs.collab_principal_key(team_id, key_sha256 bytea) → (key_id, role, state, expires_at, revoked_at)` (000020, `afs_edge` only) | afs-edge, for a team API key | The API-key form of the above; §7.2 |
| `afs.record_collab_access(rows jsonb) → integer` (000020, `afs_edge` only) | afs-edge, every 30 s | Adds five-minute counts to `collaboration_access`; §7.2 |
| `afs.emit_collab_secret_detected(team_id, surface, principal_kind, principal_id, pattern, action, count) → bigint` (000020, `afs_edge` only) | afs-edge | Writes one `collaboration.secret_detected` outbox event; §7.2 |
| `afs.ensure_collaboration_access_partition(month date) → text` (000020, `afs_reconciler`) | reconciler, monthly | Like the other `ensure_*_partition` functions |
| `afs.account_allowed(team_id, account_id) → boolean` | api, reconciler | Allowed-accounts filter |
| `afs.team_missing_required_tags(team_id, key) → text` | api | Required tags a team still lacks (for clear errors) |
| `afs.ensure_usage_partition`, `afs.ensure_activity_partition`, `afs.ensure_traffic_partition` | reconciler, monthly | Create next month's partitions ahead of time |
| `afs.tag_set_for(team_id, tags) → text`, `afs.current_team_tag_set(team_id) → text` | gateway, reconciler, billing | The snapshot id to stamp on a usage, activity, traffic or cost row; creates the set if new |
| `afs.purge_idempotency_keys() → bigint` | reconciler, every few minutes | Deletes expired keys |
| `afs.caller_sees_team`, `afs.caller_is_service_admin`, `afs.caller_is_security_operator`, `afs.caller_owns_scope`, `afs.work_order_team`, `afs.caller_owns_work_order_repo`, `afs.current_actor`, `afs.new_id` (000016, owner only) | RLS, triggers and other functions | Not called by services directly |

| `afs.schema_version() → bigint` (000017, SECURITY DEFINER, `afs_app`, `afs_reconciler`, `afs_gateway`, `afs_billing`, `afs_readonly`, and from 000020 `afs_edge`) | every service, at startup | The highest applied migration version, or 0 when none; nothing else is exposed. A service refuses to start when it is lower than the version the service was built against |

### 4.3 Outbox payload shape

The payload of an `outbox_events` row is the API contract §7 `detail`: `{id, occurredAt, teamId, agentId?, poolId?, actor, data}`.
`afs-api` writes that shape itself. Since 000019 `instantiate_work_order_team` and `record_work_order_secret` write it through
`afs.event_detail`: `team.created` with `data` `{teamId, kind: ephemeral, workOrderId}`, `pool.created` with `poolId` in the
envelope and `data` `{poolId, teamId}`, `work_order.assigned` with `data` `{workOrderId, teamId}`, and `secret.created` as above.
Rows written by `instantiate_work_order_team` before 000019 keep their old flat payload (`{teamId, kind, workOrderId}`,
`{poolId, teamId}`, `{workOrderId, teamId}`), because migrations never rewrite published history. The publisher must accept both:
a flat payload is wrapped by lifting its keys into `data`, taking `teamId` and `poolId` from the row (else the payload),
`occurredAt` from the row's `created_at` in UTC seconds, `actor` `system`, and an `id` derived from the outbox id
(`evt_` plus the id zero-padded to 26 digits, stable across redelivery so consumers can deduplicate). The wrapping can go once
no such row can exist. A mutation without an event type writes no outbox row (§5).

Change feed: `agent_secret_bindings` has a revision trigger (`afs.record_revision`, key `<team_id>/<agent_id>/<target>`, since the
table has no id column) and a notify trigger (payload `agent_secret_bindings:<team_id>:` with an empty id part, 000018), so a
restore can rebuild bindings and the reconciler's route for the table fires.

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
| `23505` unique_violation | Duplicate name, slug, issuer, pending proposal; a second collaboration agent in a team (index `agents_team_collaboration_uq`, `details.reason = collaboration_agent_exists`); a slug whose hostname is held (constraint name `collab_hostname_held`, `details.reason = hostname_held`) | `Conflict` |
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
pool deletion, audit and outbox inserts outside the caller's teams). Open after `000016`, and since closed:

- `audit_log` partitioning (OQ-4), still open.
- Swarm template `secrets`: `instantiate_work_order_team` does not create them, because a secret row needs
  the ARN Secrets Manager assigns and `afs_reconciler` may not insert `secrets` or `pool_secret_bindings`.
  Closed by `000019`: the reconciler creates each secret empty in Secrets Manager and records it with
  `afs.record_work_order_secret` (§4.2).

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
| `collab.base_domain` | `null` (unset: the feature is off) | JSON `null`, or a lower-case DNS name of 4 to 253 characters, each label 1 to 63 of `[a-z0-9-]` not starting or ending with `-` | 000020 |
| `collab.public_endpoints` | `true` | boolean | 000020 |
| `collab.allowed_source_cidrs` | `[]` | JSON array of at most 200 strings, each a valid IPv4 or IPv6 CIDR with no host bits set (`cidr` cast) | 000020 |
| `collab.session_ttl_minutes` | `480` | integer 15 to 1440 | 000020 |
| `collab.content_scan` | `"block"` | `"block"`, `"warn"`, `"off"` | 000020 |
| `collab.max_body_mb` | `25` | integer 1 to 100 | 000020 |
| `collab.denied_spike_threshold` | `50` | integer 1 to 100000 | 000020 |

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

## 7.2 Migration 000020: Paperclip team collaboration

Requirements: [Paperclip PRD](../../paperclip-team-collaboration-PRD.md) COL-1, COL-2, COL-5, COL-7, COL-12, COL-14,
COL-16 to COL-20, COL-23, COL-31, COL-36, SEC-7 and the TEAM-9 hostname hold; stories DB-US-44 to DB-US-47. Minor
release. The migration is one transaction, additive, and its header notes the lock impact of each statement. Down
reverses it (it drops the new objects and columns; it exists for local use and tests only). Decisions made here are
PC-D11 to PC-D18 (PRD §12.1).

**Pre-flight.** `bootstrap/roles.sql` gains `afs_edge` (`NOLOGIN`, created `IF NOT EXISTS` like the others). The
migration begins by checking that the role exists and fails with `55000` ("run afs-migrate bootstrap-roles") if
not, because `afs_owner` cannot create cluster roles. Operators run `afs-migrate bootstrap-roles` before deploying a
`-restapi` release that embeds 000020.

### 7.2.1 Existing tables

| Change | Definition | Lock and notes |
|---|---|---|
| `agent_templates.capabilities` | `text[] NOT NULL DEFAULT '{}'` with `CHECK (afs.capabilities_ok(capabilities))`: at most 8 elements, no duplicates, every element in the known list, which is `{paperclip}` (adding a value is a later migration, per the text-plus-CHECK rule). Written by service admins through the existing `app_write` policy | Constant default: no rewrite |
| `agents.role` | `text NOT NULL DEFAULT 'worker' CONSTRAINT agents_role_check CHECK (role IN ('worker','collaboration'))`. Existing rows become `worker` | Constant default: no rewrite; brief `ACCESS EXCLUSIVE` |
| `agents_team_collaboration_uq` | `CREATE UNIQUE INDEX ON afs.agents (team_id) WHERE role = 'collaboration' AND deleted_at IS NULL`. A second live collaboration agent raises `23505` | Plain (transactional) build takes a `SHARE` lock that blocks agent writes while it builds; `agents` is small (thousands of rows), so it is milliseconds |
| `agents` guard trigger `afs.agents_collaboration_guard()` (BEFORE INSERT OR UPDATE) | UPDATE that changes `role` → `23514`. `role = 'collaboration'` needs `template_id` not NULL on a template whose `capabilities` contains `paperclip`, `iam_identity = 'dedicated'` and a snapshot schedule other than `off`, else `23514`. `role = 'worker'` on a `paperclip` template → `23514` | Messages name the failed rule for people |
| `agent_templates` guard trigger `afs.agent_templates_capability_guard()` (BEFORE UPDATE) | Removing `paperclip` while a live collaboration agent uses the template, or adding it while a live worker agent does → `55000` | |
| `agents` cleanup trigger `afs.agents_collaboration_cleanup()` (AFTER UPDATE OF `state`, `deleted_at`; SECURITY DEFINER) | When a collaboration agent leaves `enabled` and `paused` (state `deleting` or `deleted`): deletes its `team_collaboration` row (so the route disappears) and sets `agent_collaboration.connect = false` for every agent of the team (link rows stay; the reconciler revokes keys and sets `link_state = 'disabled'`). Fires the revision and change-feed triggers | |
| `teams.may_expose_collaboration` | `boolean NOT NULL DEFAULT true`. The guard trigger of 000013 lists it with the service-admin-only columns: any other caller changing it → `42501` | Constant default |
| `identity_providers.collab_client_id`, `collab_client_secret_arn` | `collab_client_id text` nullable, `CHECK (collab_client_id ~ '^[A-Za-z0-9._:@-]{1,255}$')`; `collab_client_secret_arn text` nullable, `CHECK (… LIKE 'arn:aws%:secretsmanager:%:secret:%')`; `CHECK (collab_client_secret_arn IS NULL OR collab_client_id IS NOT NULL)`. A reference, never a value. Written by service admins through the existing policy | Nullable columns |
| `role_bindings.role`, `api_keys.role` | Both CHECKs accept `team_collaborator`. `role_bindings_check` and `api_keys_scope_check` already tie service-level roles to a NULL team, so `team_collaborator` with no team → `23514` | Constraints replaced `NOT VALID` then `VALIDATE` |
| `secrets.managed_by` | `text NOT NULL DEFAULT 'user' CHECK (managed_by IN ('user','afs','paperclip'))`; see §7.2.4 | Constant default |
| `service_settings` | Range check of 000013 replaced (`NOT VALID` then `VALIDATE`) to cover the seven `collab.*` keys of §7.0, using helper `afs.cidr_list_ok(jsonb)` and `afs.dns_name_ok(jsonb)`; rows seeded with the defaults of §7.0 (`collab.base_domain` seeded as JSON `null`). A value outside a range → `23514` | |
| `afs.drop_partitions_older_than(months)` | Replaced: also drops `collaboration_access` partitions (still never `audit_log`). Returns the dropped names as before | |
| `afs.schema_version()` | `EXECUTE` also granted to `afs_edge` | |

### 7.2.2 `team_collaboration` (desired state, one row per team that has a collaboration agent)

| Column | Type | Rules |
|---|---|---|
| `team_id` | `text` | `PRIMARY KEY`, `REFERENCES afs.teams (id) ON DELETE CASCADE` |
| `agent_id` | `text NOT NULL` | `FOREIGN KEY (team_id, agent_id) REFERENCES afs.agents (team_id, id)`; a constraint trigger requires that agent's `role = 'collaboration'` (`23514`) |
| `web_ui_enabled` | `boolean NOT NULL DEFAULT true` | The team's stored choice (COL-20) |
| `rest_api_enabled` | `boolean NOT NULL DEFAULT false` | The team's stored choice |
| `registration_mode` | `text NOT NULL DEFAULT 'manual'` | `CHECK IN ('manual','managed')` |
| `version`, `generation`, `created_at`, `created_by`, `updated_at` | as other desired-state tables | `afs.touch_row()`, generation bump, `afs.record_revision()` (key `<team_id>`, since the table has no `id` column, like `agent_secret_bindings`), `afs.notify_desired_state()` (payload `team_collaboration:<team_id>:<team_id>`) |

`afs-api` inserts the row in the same transaction as the collaboration agent, and the cleanup trigger above deletes it.
The database stores the team's choice and does not check guardrails: the guardrails (`collab.base_domain`,
`collab.public_endpoints`, `teams.may_expose_collaboration`) apply when the route is computed, so turning one off keeps
the stored choice (COL-20). `resource_status` carries the reconciler's conditions (`EndpointReady`, `PaperclipReady`,
`RegistrationHealthy`, `UnmanagedPaperclipAgents`) under `resource_kind = 'team_collaboration'`, `resource_id = team_id`.
RLS: `ENABLE ROW LEVEL SECURITY`, policy `app_team` for `afs_app` on `afs.caller_sees_team(team_id)` (all commands),
`service_roles_all` for the service roles.

### 7.2.3 `agent_collaboration` (desired state plus link status, one row per worker agent that was ever connected)

| Column | Type | Rules |
|---|---|---|
| `team_id`, `agent_id` | `text NOT NULL` | `PRIMARY KEY (team_id, agent_id)`, `FOREIGN KEY (team_id, agent_id) REFERENCES afs.agents (team_id, id)`; the agent must be `role = 'worker'` (`23514`) |
| `connect` | `boolean NOT NULL` | `true` while the team has no `team_collaboration` row → `55000` (`Conflict`) |
| `paperclip_agent_id` | `text` | `CHECK (paperclip_agent_id ~ '^[A-Za-z0-9._:-]{1,128}$')`. A change by any role other than `afs_reconciler` while the team's `registration_mode = 'managed'` → `55000` |
| `link_state` | `text NOT NULL` | `CHECK IN ('pending','linked','failed','disabled')`. Set by trigger on insert and on a change of `connect` (`pending` when `connect` becomes true, `disabled` when false); thereafter only `afs_reconciler` changes it |
| `last_synced_at` | `timestamptz` | Reconciler only |
| `last_error` | `text` | `CHECK (length(last_error) <= 500)`; reconciler only; never contains a Paperclip key or content |
| `version`, `generation`, `created_at`, `created_by`, `updated_at` | as above | revision key `<team_id>/<agent_id>`, notify payload `agent_collaboration:<team_id>:<agent_id>`. A change of `connect` bumps `generation` so the reconciler rolls the pod |

An agent with no row reads as `connect = false`, `link_state = 'disabled'`; agents that predate the collaboration agent
are therefore not connected (COL-10) and there is no backfill. `afs-api` upserts the row (`INSERT … ON CONFLICT DO UPDATE`).
Column grants enforce who writes what (§7.2.6). RLS as `team_collaboration`.

### 7.2.4 Managed secrets and reserved names

`secrets.managed_by` and trigger `afs.secrets_managed_guard()` (BEFORE INSERT OR UPDATE OR DELETE):

| Secret name | `managed_by` allowed | Scope and ARN |
|---|---|---|
| `paperclip` | none (`23514`): it would sit beside the `paperclip/` prefix | |
| `paperclip-better-auth-secret`, `paperclip-tool-action-signing-secret`, `paperclip-secrets-master-key`, `paperclip-board-api-key` | `afs` | agent scope, the team's collaboration agent only; normal managed path |
| `paperclip-agent-api-key` | `user` (manual registration) or `afs` (managed registration) | agent scope, a worker agent; normal managed path |
| any other `paperclip-*` | `paperclip` | agent scope, the collaboration agent; the ARN's path part must start with `afs.secret_path(team_id, agent_id, 'paperclip') \|\| '/'`; `origin = 'registered'` (Paperclip created it, so the managed-path recompute of the insert trigger does not apply) |
| every other name | `user` | as today |

Anything else → `23514`. For `paperclip` rows, `name` is `paperclip-` plus the path suffix lower-cased with characters
outside `[a-z0-9-]` replaced by `-`, cut to 63 characters, and made unique with a `-<4 hex>` suffix on collision, so the
existing `UNIQUE (team_id, name)` keeps holding (PC-D11). `afs_reconciler` is the only writer of `paperclip` rows;
`afs_app` cannot insert or update one (policy and column grant) and `afs_reconciler` cannot write any other secret row
(`42501`). An `agent_secret_bindings` insert for a `paperclip` secret → `23514`. `afs`-managed boot secrets are bound by
`afs-api` in the `CreateAgent` transaction. The agent's secret path and IAM prefix rules are unchanged; the collaboration
agent's role additionally may write and delete only below `.../<agent>/paperclip/` (SEC-7), which is an IAM matter for
`-restapi`.

### 7.2.5 Edge role, functions and fact table

Role `afs_edge` holds `USAGE` on schema `afs`, `EXECUTE` on exactly the functions below (revoked from `PUBLIC`), and no
table privilege. It may `LISTEN afs_desired_state`. All functions are `SECURITY DEFINER`, owned by `afs_owner`, with
`SET search_path = pg_catalog, afs`, and return only the named columns.

**`afs.collab_routes()`** returns one row per team that is not `deleting` or `deleted` and has a `team_collaboration` row:

| Column | Type | Meaning |
|---|---|---|
| `team_id`, `slug`, `namespace` | `text` | |
| `hostname` | `text` | `slug || '.' || collab.base_domain`; NULL when the base domain is unset |
| `team_state` | `text` | `active` or `suspended` |
| `agent_id`, `agent_state` | `text` | the collaboration agent; `enabled`, `paused`, `deleting` |
| `web_ui_enabled`, `rest_api_enabled` | `boolean` | stored choices |
| `web_ui_effective`, `rest_api_effective` | `boolean` | stored choice AND `teams.may_expose_collaboration` AND `collab.public_endpoints` AND base domain set AND (for the web UI) the provider has `collab_client_id` |
| `may_expose` | `boolean` | the guardrail |
| `ready` | `boolean` | `team_state = 'active'`, `agent_state = 'enabled'` and `resource_status` condition `EndpointReady = True` |
| `not_ready_reason` | `text` | NULL when ready; else `team_suspended`, `paused` or `starting` (anything else, including a deleting agent, is `starting`) |
| `service_name`, `port` | `text`, `integer` | `paperclip`, `3100` |
| `provider_id`, `issuer_url`, `groups_claim` | `text` | the team's provider, else the default provider |
| `collab_client_id`, `collab_client_secret_arn` | `text` | NULL when the provider has none |

**`afs.collab_settings()`** returns `(key text, value jsonb)` for the seven `collab.*` keys only.

**`afs.collab_principal(p_team_id text, p_subject text, p_provider_id text, p_groups text[])`** returns
`(binding_id text, role text, subject_type text, user_id text)`: the `team_admin`, `team_viewer` and `team_collaborator`
bindings on that team and the `service_admin` bindings that match the person, by the rules of `afs-api` (D21): a user
binding matches on the user whose `sub` and provider equal the arguments (`user_id` is NULL when no such user row exists
yet); a group binding matches when `p_groups` contains `group_name` and `p_provider_id` is the team's effective provider
(service-level group bindings: the provider they name). No `security_operator` row is ever returned. `p_groups` is
limited to 500 entries (`22023` beyond).

**`afs.collab_principal_key(p_team_id text, p_key_sha256 bytea)`** returns
`(key_id text, role text, state text, expires_at timestamptz, revoked_at timestamptz)`: no row for an unknown hash, for a
service-level key, or for a key of another team (a key never reveals other teams); `state` is `active`, `expired` or
`revoked`; sets `last_used_at` at most once a minute for a usable key. Never returns the hash.

**`afs.record_collab_access(p_rows jsonb) → integer`** takes an array of at most 1000 objects `{bucket_start, team_id,
surface, principal_kind, principal_id, outcome, service_admin_entry, requests, bytes}` and adds each to
`collaboration_access` with `INSERT … ON CONFLICT DO UPDATE SET requests = requests + EXCLUDED.requests, bytes = bytes +
EXCLUDED.bytes`. A `bucket_start` not on a five-minute boundary or outside `now() - 1 day … now() + 5 minutes` → `22023`;
unknown values → `23514`; rows for an unknown team are skipped. Returns the number of rows applied. It writes counts
only, never a body, path or header.

**`afs.emit_collab_secret_detected(p_team_id text, p_surface text, p_principal_kind text, p_principal_id text, p_pattern
text, p_action text, p_count integer) → bigint`** writes one `outbox_events` row of type `collaboration.secret_detected`
with the API contract §7 envelope through `afs.event_detail` (actor `system:edge`) and returns the outbox id.
`p_pattern` is one of `aws_access_key`, `github_token`, `slack_token`, `private_key`, `jwt`, `okta_client_secret`,
`entra_client_secret`, `generic_assignment`; `p_action` is `blocked` or `warned`; there is no parameter that could carry a
value or fragment. It can write no other event type (PC-D16).

**`collaboration_access`** (fact table, partitioned by month on `bucket_start`, 13-month retention like the other fact
tables, D36; `afs.ensure_collaboration_access_partition(month)` creates partitions ahead, a default partition catches
strays):

| Column | Type | Rules |
|---|---|---|
| `bucket_start` | `timestamptz NOT NULL` | `CHECK (extract(epoch FROM bucket_start)::bigint % 300 = 0)` |
| `team_id` | `text NOT NULL` | no foreign key (facts outlive the team, like `agent_activity`) |
| `surface` | `text NOT NULL` | `IN ('web_ui','rest_api')` |
| `principal_kind` | `text NOT NULL` | `IN ('user','api_key','anonymous')` |
| `principal_id` | `text NOT NULL` | `usr_…` or `key_…`; `''` exactly when `anonymous` (a person's name is never stored) |
| `outcome` | `text NOT NULL` | `IN ('signed_in','signed_out','allowed','secret_warned','denied_unauthenticated','denied_forbidden','denied_surface_disabled','denied_secret_detected','denied_bad_request','throttled','unavailable')` |
| `service_admin_entry` | `boolean NOT NULL DEFAULT false` | true when the person had access only as a service admin (COL-31) |
| `requests` | `integer NOT NULL` | `> 0` |
| `bytes` | `bigint NOT NULL DEFAULT 0` | `>= 0` |
| `recorded_at` | `timestamptz NOT NULL DEFAULT now()` | |

Primary key `(bucket_start, team_id, surface, principal_kind, principal_id, outcome, service_admin_entry)`; index on
`(team_id, bucket_start)`. Denied-spike counting (COL-30) uses outcomes `denied_unauthenticated`, `denied_forbidden`,
`denied_surface_disabled` and `denied_secret_detected`. Reports (COL-36) read the table directly; there is no rollup.
RLS: `ENABLE ROW LEVEL SECURITY`, `SELECT` policy for `afs_app` on `afs.caller_sees_team(team_id)`, `service_roles_all`.

**`collab_hostname_holds`** (TEAM-9, PC-D9): `slug text PRIMARY KEY`, `team_id text NOT NULL` (no foreign key),
`held_until timestamptz NOT NULL`, `created_at timestamptz NOT NULL DEFAULT now()`. An AFTER UPDATE trigger on `teams`
inserts (or extends) a hold of `now() + 30 days` when `deleted_at` is set on a team that has a `team_collaboration` row.
A BEFORE INSERT trigger on `teams` refuses a slug with an unexpired hold held for a different `team_id` with `23505`
(constraint name `collab_hostname_held`). `teams.slug` is `UNIQUE` across deleted rows today, which already refuses reuse;
the hold keeps the rule explicit and survives any later purge of deleted team rows. The reconciler deletes expired
holds daily; there is no early release in this release (PC-D11).

### 7.2.6 Grants by role

| Object | `afs_app` | `afs_reconciler` | `afs_edge` | `afs_billing` | `afs_readonly` | `afs_gateway` |
|---|---|---|---|---|---|---|
| `team_collaboration` | `SELECT`; `INSERT (team_id, agent_id, web_ui_enabled, rest_api_enabled, registration_mode)`; `UPDATE (web_ui_enabled, rest_api_enabled, registration_mode)`; no `DELETE` | `SELECT` | none | none | `SELECT` | none |
| `agent_collaboration` | `SELECT`; `INSERT (team_id, agent_id, connect, paperclip_agent_id)`; `UPDATE (connect, paperclip_agent_id)` | `SELECT`; `UPDATE (paperclip_agent_id, link_state, last_synced_at, last_error)` | none | none | `SELECT` | none |
| `collaboration_access` | `SELECT` (RLS) | `SELECT`; `EXECUTE ensure_collaboration_access_partition`, `drop_partitions_older_than` | via `record_collab_access` only | none | `SELECT` | none |
| `collab_hostname_holds` | `SELECT` | `SELECT`, `DELETE` | none | none | `SELECT` | none |
| `secrets` | `INSERT` and `UPDATE` as today, with `managed_by` insertable as `user` or `afs` only and not updatable; no write to `paperclip` rows | `INSERT`, `UPDATE`, `DELETE` on `managed_by = 'paperclip'` rows only; `SELECT` all as today | none | none | `SELECT` | none |
| `agent_templates.capabilities`, `teams.may_expose_collaboration`, `identity_providers.collab_*`, `service_settings` `collab.*` | as the table today (service admins only where the guard says so) | `SELECT` | via the functions | `SELECT` on `service_settings` as today | `SELECT` | none |
| functions of §7.2.5 | none | `ensure_collaboration_access_partition` | all but the partition function | none | none | none |

`afs_billing` and `afs_gateway` get nothing new: the collaboration agent calls the gateway like any agent, and the
collaboration report is on demand only (PC-D13). The reconciler's access to Paperclip's board key is the existing
read of `secrets` plus an IAM condition in `-restapi`.

### 7.2.7 Change feed, RLS and tests

- Change feed (D30): notify triggers on `team_collaboration` and `agent_collaboration`; `teams`, `agents`, and
  `identity_providers` already notify, which covers `may_expose_collaboration`, the role of an agent and provider
  changes. `service_settings` has no `generation`, so a setting change reaches the edge at its next 30-second poll.
- Revisions: `team_collaboration` and `agent_collaboration` have revision triggers; `collaboration_access` and
  `collab_hostname_holds` do not.
- RLS: both desired-state tables and `collaboration_access` as above; the new team-owned tables get rows in
  `seedOtherTeams`, and `collaboration_access` gets rows for another team in the read-isolation test.
- Tests: `TestCollaborationAgent/*` (second insert `23505`, role change `23514`, template, identity and snapshot checks,
  capability removal `55000`), `TestTeamCollaboration/*`, `TestAgentCollaboration/*`, `TestManagedSecrets/*` (reserved
  names, binding refusal, reconciler write scope), `TestServiceSettingRanges/collab.*`,
  `TestRowLevelSecurityIsolatesTeams/team_collaboration`, `TestCrossTeamWritesChangeNothing/team_collaboration`,
  `TestEdgeRole/*` (no direct select on any table; each function returns only its named columns; `emit_collab_secret_detected`
  writes no other type), `TestCollaborationAccess/*` (alignment, additive upsert, retention), `TestHostnameHold/*`, and
  up/down/up with checksums.

## 8. Change process

1. Schema change: a `-db` PR with the migration, integration tests (rejected case for every new
   constraint; RLS isolation for every new team table), `docs/data-model.md`, and this contract when §2
   to §6 change. Tag a release after merge.
2. `-restapi` adopts the tag in its own PR (`go get …@vX.Y.Z`), with repository tests against the new
   schema.
3. A breaking change follows expand and contract across two `-db` releases.
