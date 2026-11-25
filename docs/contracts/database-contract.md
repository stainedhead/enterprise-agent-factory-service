# Database contract: `-db` ↔ `-restapi`

| | |
|---|---|
| **Status** | Contract **v1.6.0** (2026-11-25) adds migration **000024** (governed MCP servers, policy, ledger and federated identities, [mcp-gateway-PRD.md](../../mcp-gateway-PRD.md) Appendix E.2, specified in §7.5; release 1.3.0, lockstep with `-restapi`). Contract v1.5.0 (2026-11-25) adds migration **000023** (team model gateway, routes and provider switches, [model-endpoint-gateway-PRD.md](../../model-endpoint-gateway-PRD.md) Appendix D.2, specified in §7.4; release 1.2.0, lockstep with `-restapi`). Contract v1.4.0 (2026-11-23) adds migration **000022** (team orchestration agent and model access, [team-orchestration-agent-PRD.md](../../team-orchestration-agent-PRD.md) DB-US-58 to DB-US-61, specified in §7.3; release 1.1.0, lockstep with `-restapi`); not yet built. Contract v1.3.2 (2026-11-22) at schema 000021: migration 000020 (Paperclip team collaboration, [paperclip-team-collaboration-PRD.md](../../paperclip-team-collaboration-PRD.md) DB-US-44 to DB-US-47, specified in §7.2) and 000021 (`collab_routes()` provider client ids, §7.2.10) are built in `-db` at `main` (0d87776) and ship in release 1.0.1, which `-db` and `-restapi` share. Earlier history: contract v1 at schema 000019. Corrected on 2026-11-22 (contract corrections round, PC-D20 to PC-D31) to match the `-db` PRD §9.1 decisions DB-D1 to DB-D16 and the `-restapi` gaps G1 to G10. 000013 implements root PRD decisions D30, D31, D33 to D36 and D45; some D35 rules landed in 000011 and 000012, as marked below. 000014 implements D54 (agent template catalog) and D49 (export and import transport). 000015 closes the gaps that proving the `-db` PRD revealed; 000016 adds the service access paths `-restapi` requested (X-DB-1 to X-DB-6). 000017 adds `afs.schema_version()` for the startup check of services that cannot read the tracking table, and `identity_providers.cli_client_id` (the CLI public client, D48; `client_id` is the console client). Planned first release containing 000011 to 000017: `v0.13.0` 000018 adds daily report rollups and the follow-ups `-restapi` asked for (X-DB-8 to X-DB-10, `agent_secret_bindings` triggers, ETag-stable report schedules); 000019 adds `afs.record_work_order_secret` (template secrets for remediation teams) and `afs.event_detail`, and gives the outbox payloads written by `afs.instantiate_work_order_team` the API contract §7 envelope. Schema 000019 is at `-db` `main` (83f0345) and is not yet tagged; `-restapi` pins its pseudo-version until the tag exists |
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
| `afs_gateway` | `afs-gateway` | Read teams, agents, pools, models (incl. `max_output_tokens`), prices, budgets, effective tags; (000022) `agent_models`, `pool_models`, `team_inference_profiles`, `service_settings (key, value)`, the view `afs.effective_agent_models` and `afs.model_admission` (§7.3.5); `ensure_spend_counter`, `reserve_spend_held` / `settle_reservation` (and the older `reserve_spend` / `settle_spend`); insert `usage_events` (stamped with `tag_set_id`), tag sets, threshold events, outbox; `resolve_workload` (000016) | Anything else |
| `afs_billing` | `afs-billing` | Read usage, teams, agents, models, prices, budgets, activity, traffic; write `cost_daily`, `cost_reconciliations`, `cost_allocation_tag_status`, tag sets; insert and supersede `model_price_proposals`; (000018) read `service_settings (key, value)` and `team_models (team_id, model_id, inference_profile_arn)` and the daily rollups; read `report_schedules` and `notification_channels` and update a schedule's run columns; insert outbox | Approve prices; change desired state |
| `afs_edge` (000020) | `afs-edge` | `EXECUTE` on the ten `SECURITY DEFINER` functions of §7.2.5 and §7.2.8, (000022) `afs.orchestration_routes()` and `afs.orchestration_settings()` (§7.3.6), and `afs.schema_version()`; `LISTEN afs_desired_state` | Any table privilege, any other function |
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
| `secrets` rows with `managed_by = 'paperclip'` (000020) | R | I, U, D (only such rows; trigger `42501` for any other secret row), plus the `afs`-managed key rows only through the three `record_collab_*` / `remove_collab_agent_key` functions (§7.2.6) | — | — |
| `collab_edge_sessions`, `collab_edge_handoffs` (000020, §7.2.8) | — | F `purge_collab_edge_sessions` | via the `collab_session_*` and `collab_handoff_*` functions only (`afs_edge`) | — |
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
| `afs.collab_session_get(id_hash)`, `collab_session_revoke(id_hash)`, `collab_handoff_create(...)`, `collab_handoff_consume(code_hash, host, session_id_hash)` (000020, `afs_edge` only) | afs-edge | Server-side edge sessions and the single-use handoff; §7.2.8 |
| `afs.purge_collab_edge_sessions() → bigint` (000020, `afs_reconciler`) | reconciler, hourly | Deletes expired and revoked sessions and expired handoffs |
| `afs.record_collab_agent_key(team_id, agent_id, secret_arn) → text`, `afs.remove_collab_agent_key(team_id, agent_id) → boolean`, `afs.record_collab_board_key(team_id, collab_agent_id, secret_arn) → text` (000020, `afs_reconciler` only) | reconciler, managed registration | Record and remove the `afs`-managed Paperclip key secrets and their binding; §7.2.6 |
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
must branch on `code`. 000022 adds the constraint-name mapping of §7.3.9; from 000022 the second collaboration agent case above reads `agents_team_orchestration_uq` (`orchestration_agent_exists`).

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
| `collab.base_domain` | `null` (unset: the feature is off) | JSON `null`, or a lower-case DNS name of at least two labels, 4 to 253 characters, each label 1 to 63 of `[a-z0-9-]` not starting or ending with `-` | 000020 |
| `collab.public_endpoints` | `true` | boolean | 000020 |
| `collab.allowed_source_cidrs` | `[]` | JSON array of at most 100 strings, each a valid IPv4 or IPv6 CIDR with no host bits set (`cidr` cast) | 000020 |
| `collab.session_ttl_minutes` | `480` | integer 15 to 1440 | 000020 |
| `collab.content_scan` | `"block"` | `"block"`, `"warn"`, `"off"` | 000020 |
| `collab.max_body_mb` | `25` | integer 1 to 100 | 000020 |
| `collab.denied_spike_threshold` | `50` | integer 1 to 100000 | 000020 |
| `orchestration.tools` | see §7.3.4 | each tool once with its fixed profile; exactly one default, enabled; template has `orchestration` and `tool:<tool>` | 000022 |
| `orchestration.public_base_domain` | copy of `collab.base_domain` | as `collab.base_domain`; `collab.base_domain` becomes its read-only alias | 000022 |
| `orchestration.private_base_domain` | `null` | as `collab.base_domain` | 000022 |
| `orchestration.public_endpoints` | copy of `collab.public_endpoints` | boolean; `collab.public_endpoints` becomes its read-only alias | 000022 |
| `orchestration.private_endpoints` | `true` | boolean | 000022 |
| `orchestration.default_limit`, `.default_web_ui_exposure` | `"public"` when `collab.base_domain` is set at migration, else `"private"` (OR-D5) | `"off"`, `"private"`, `"public"`; levels not above the limit | 000022 |
| `orchestration.default_web_api_exposure` | `"off"` | as above | 000022 |
| `orchestration.default_resources` | `{"cpu": "1", "memory": "4Gi"}` | resources object | 000022 |
| `orchestration.default_volume_gib` | `20` | integer 10 to 1000 | 000022 |
| `models.service_access` | `"selected"` on an upgraded database (models exist), `"all"` on a fresh one | `"all"`, `"selected"` | 000022 |
| `models.default_team_access` | `"all"` | `"all"`, `"selected"` | 000022 |
| `models.default_team_models` | `[]` | array of at most 100 existing model ids | 000022 |
| `models.default_model_id` | `null` | `null` or an existing model id | 000022 |

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
PC-D11 to PC-D31 (PRD §12.1); the corrections of 2026-11-22 follow the `-db` PRD §9.1 (DB-D1 to DB-D16) and are marked below.

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
| `agents` guard trigger `afs.agents_collaboration_guard()` (BEFORE INSERT OR UPDATE) | UPDATE that changes `role` → `23514`. `role = 'collaboration'` needs `template_id` not NULL on a template whose `capabilities` contains `paperclip`, `iam_identity = 'dedicated'` and a snapshot schedule other than `off`, else `23514`. The column default of the retention count is not changed (DB-D16): the database enforces only "not off" and `afs-api` sets 14 for the role. `role = 'worker'` on a `paperclip` template → `23514` | Messages name the failed rule for people |
| `agent_templates` guard trigger `afs.agent_templates_capability_guard()` (BEFORE UPDATE) | Removing `paperclip` while a live collaboration agent uses the template, or adding it while a live worker agent does → `55000` | |
| `agents` cleanup trigger `afs.agents_collaboration_cleanup()` (AFTER UPDATE OF `state`, `deleted_at`; SECURITY DEFINER) | When a collaboration agent leaves `enabled` and `paused` (state `deleting` or `deleted`): deletes its `team_collaboration` row (so the route disappears) and sets `agent_collaboration.connect = false` for every agent of the team (link rows stay; the reconciler revokes keys and sets `link_state = 'disabled'`). Fires the revision and change-feed triggers | |
| `teams.may_expose_collaboration` | `boolean NOT NULL DEFAULT true`. 000020 drops and recreates `teams_guardrail_guard` (`BEFORE UPDATE OF <column list>`) with the column added and replaces its function with the extra condition (DB-D6): any other caller changing it → `42501` | Constant default |
| `identity_providers.collab_client_id`, `collab_client_secret_arn` | `collab_client_id text` nullable, `CHECK (collab_client_id ~ '^[A-Za-z0-9._:@-]{1,255}$')`; `collab_client_secret_arn text` nullable, checked with the same Secrets Manager ARN regex of 000009 as `client_secret_arn` (DB-D14, so one parser serves both); `CHECK (collab_client_secret_arn IS NULL OR collab_client_id IS NOT NULL)`. A reference, never a value. Written by service admins through the existing policy | Nullable columns |
| `role_bindings.role`, `api_keys.role` | Both CHECKs accept `team_collaborator`. `role_bindings_check` and `api_keys_scope_check` already tie service-level roles to a NULL team, so `team_collaborator` with no team → `23514` | Constraints replaced `NOT VALID` then `VALIDATE` |
| `secrets.managed_by` | `text NOT NULL DEFAULT 'user' CHECK (managed_by IN ('user','afs','paperclip'))`; see §7.2.4 | Constant default |
| `service_settings` | One new constraint `service_settings_collab_check` (`NOT VALID` then `VALIDATE`) covers the seven `collab.*` keys of §7.0 with `IMMUTABLE` helpers `afs.cidr_list_ok(jsonb)` and `afs.dns_name_ok(jsonb)`; the existing range constraints (`_pricing_`, `_idempotency_`, `_swarm_`, `_runtime_`, `_work_order_team_`) are not touched (DB-D7); rows seeded with the defaults of §7.0 (`collab.base_domain` seeded as JSON `null`). A value outside a range → `23514` | |
| `afs.instantiate_work_order_team(work_order_id)` | Extended for swarm templates with a `collaboration` entry (§7.2.9, PC-D29) | |
| `afs.record_work_order_secret(...)` | Extended to record a boot secret of the collaboration agent (§7.2.9) | |
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
| `version`, `generation`, `created_at`, `created_by`, `updated_at` | as other desired-state tables | `afs.touch_row()` (bumps `version` only), a BEFORE UPDATE trigger that bumps `generation` when `web_ui_enabled`, `rest_api_enabled` or `registration_mode` changes (DB-D1: the database, not the API, guarantees the roll), `afs.record_revision()` (key `<team_id>`, since the table has no `id` column, like `agent_secret_bindings`), `afs.notify_desired_state()` with payload `team_collaboration:<team_id>:` (empty id part, DB-D2; the reconciler re-reads the team) |

`afs-api` inserts the row in the same transaction as the collaboration agent, and the cleanup trigger above deletes it.
A replacement collaboration agent is refused with `23505` (`agents_team_collaboration_uq`, which keys on `deleted_at IS NULL`) until the reconciler marks the old one `deleted`, although the route row is already gone; `afs-api` answers `409` meanwhile (DB-D15, no second index).

The database stores the team's choice and does not check guardrails: the guardrails (`collab.base_domain`,
`collab.public_endpoints`, `teams.may_expose_collaboration`) apply when the route is computed, so turning one off keeps
the stored choice (COL-20). `resource_status` carries the reconciler's conditions (`EndpointReady`, `PaperclipReady`,
`RegistrationHealthy`, `UnmanagedPaperclipAgents`) under `resource_kind = 'team_collaboration'`, `resource_id = team_id`.
RLS: `ENABLE ROW LEVEL SECURITY`, policy `app_team_scope` (DB-D8, the name every team-owned table uses) for `afs_app` on `afs.caller_sees_team(team_id)` (all commands),
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
| `version`, `generation`, `created_at`, `created_by`, `updated_at` | as above | revision key `<team_id>/<agent_id>`, notify payload `agent_collaboration:<team_id>:` (empty id part, DB-D2). A BEFORE UPDATE trigger bumps `generation` when `connect` or `paperclip_agent_id` changes (DB-D1: `PAPERCLIP_AGENT_ID` is an env var of the pod), so the reconciler rolls the pod |

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

Anything else → `23514`. Corrected to the existing schema (DB-D3 to DB-D5, DB-D11, DB-D12):

- **Origin and path.** `secrets_origin_check` (000003) allows only `managed`; 000020 widens it to `managed` and `registered` and adds `secrets_registered_paperclip_check` (a `registered` row must be `managed_by = 'paperclip'`). `afs.secrets_managed_path` recomputes `path` from the name for every `managed` insert; for `paperclip` rows the trigger derives `path` from the ARN instead and checks it starts with the prefix above.
- **Name.** `UNIQUE (team_id, name)` no longer exists (000003 dropped it; a secret's identity is its `path`). For `paperclip` rows the trigger computes `name` as `paperclip-` plus the path suffix lower-cased with characters outside `[a-z0-9-]` replaced by `-`, cut to 63 characters, with a `-<4 hex>` suffix on collision. A partial unique index `secrets_paperclip_name_uq ON (team_id, agent_id, name) WHERE managed_by = 'paperclip'` backs it so T4 shows stable names.
- **Who writes.** A guard trigger, not a policy, enforces it (the existing `service_roles_all` policy is `USING (true)` and a restrictive policy would silently filter an `UPDATE` or `DELETE`): `afs.secrets_managed_guard()` raises `42501` for an `afs_reconciler` write to a row that is not `managed_by = 'paperclip'` and for an `afs_app` write to a `paperclip` row. The reconciler's only other secret writes are the three `SECURITY DEFINER` functions of §7.2.6. `afs_app` inserts the `afs`-managed boot secrets in the `CreateAgent` transaction. `afs_app` deleting a boot secret of a live collaboration agent → `55000` (metadata updates are allowed; the rotation rules of COL-7 stay in `-restapi`).
- An `agent_secret_bindings` insert for a `paperclip` secret → `23514`.
- The agent's secret path and IAM prefix rules are unchanged; the collaboration agent's role additionally may write and delete below `.../<agent>/paperclip/` (SEC-7) and `PutSecretValue` on the one exact ARN of `paperclip-board-api-key` (PC-D26), which are IAM matters for `-restapi`.

### 7.2.5 Edge role, functions and fact table

Role `afs_edge` holds `USAGE` on schema `afs`, `EXECUTE` on exactly the functions below and in §7.2.8 (revoked from `PUBLIC`), and no
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
binding matches on the user with `users.oidc_issuer` equal to the `issuer_url` of `p_provider_id` and `users.oidc_subject = p_subject`, excluding users with `disabled_at` set (DB-D9; `user_id` is NULL when no such user row exists yet); a group binding matches when `p_groups` contains `group_name` and `p_provider_id` is the team's effective provider
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
with the API contract §7 envelope through `afs.event_detail` (actor `system:edge`; `aggregate_kind` `team_collaboration`, `aggregate_id` the team id, DB-D13) and returns the outbox id.
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
inserts (or extends) a hold of `now() + 30 days` when `deleted_at` is set on a team that has ever had a collaboration agent (any `agents` row with `role = 'collaboration'`, deleted ones included; DB-D10, because the cleanup trigger removes the `team_collaboration` row earlier).
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
| functions of §7.2.5 and §7.2.8 | none | `ensure_collaboration_access_partition`, `purge_collab_edge_sessions`, `record_collab_agent_key`, `remove_collab_agent_key`, `record_collab_board_key` | the ten edge functions | none | none | none |
| `collab_edge_sessions`, `collab_edge_handoffs` | none | none (purge function only) | none (functions only) | none | none (the hashes are credentials) | none |

`afs_billing` and `afs_gateway` get nothing new: the collaboration agent calls the gateway like any agent, and the
collaboration report is on demand only (PC-D13). The reconciler reads Paperclip's board key secret row with its
existing read of `secrets` plus an exact-name IAM condition in `-restapi`.

**Key rows written by the reconciler (G6, PC-D25).** In `managed` registration the reconciler cannot insert `afs`-managed
rows directly (the guard of §7.2.4); it calls three `SECURITY DEFINER` functions (`afs_reconciler` only, `afs_app` gets
`42501`), each writing an audit record (`actor_type` `system`, `actor_id` `afs.current_actor()`, no value) and no outbox row:

- **`afs.record_collab_agent_key(p_team_id text, p_agent_id text, p_secret_arn text) → text`**: for a live worker agent whose
  `agent_collaboration.connect` is true in a team with `registration_mode = 'managed'`, upserts the agent's secret row
  `paperclip-agent-api-key` (`managed_by = 'afs'`, `origin = 'managed'`, agent scope, `description` empty) and its
  `agent_secret_bindings` row (`delivery` `env`, `target` `PAPERCLIP_AGENT_API_KEY`). The ARN must match the 000009 regex with
  a path equal to `afs.secret_path(team_id, agent_id, 'paperclip-agent-api-key')`. Returns the secret id; idempotent (an
  existing row is updated with the new ARN, so a rotation reuses it). Audit `RecordCollabAgentKey`. Errors: unknown agent
  `P0002`; agent not connected, not a worker, or registration `manual` `55000`; bad ARN `23514`.
- **`afs.remove_collab_agent_key(p_team_id text, p_agent_id text) → boolean`**: removes that binding and secret row; true when
  anything was removed. The reconciler deletes the secret in Secrets Manager itself. Audit `RemoveCollabAgentKey`.
- **`afs.record_collab_board_key(p_team_id text, p_collab_agent_id text, p_secret_arn text) → text`**: records
  `paperclip-board-api-key` on the team's live collaboration agent (`managed_by = 'afs'`, agent scope, path equal to
  `afs.secret_path(team_id, collab_agent_id, 'paperclip-board-api-key')`) and **never** a binding: no environment variable of
  any agent carries it. Returns the secret id; idempotent. Audit `RecordCollabBoardKey`. Errors as above (`55000` when the agent
  is not a live collaboration agent of the team).

### 7.2.8 Edge sessions and handoff (G2, G3, PC-D22)

The edge keeps sessions server-side, so a cookie holds only an opaque id and a single-use handoff holds across any number
of replicas. Two tables with no grant to any role: all access is through `SECURITY DEFINER` functions, so `afs_edge` holds no
table privilege and `afs_readonly` cannot read the hashes (they are credentials). RLS is enabled with no policy for `afs_app`;
the owner-run functions bypass it.

**`collab_edge_sessions`**: `id_hash bytea PRIMARY KEY CHECK (length(id_hash) = 32)` (SHA-256 of a random 256-bit id; the id
itself is never stored), `team_id text NOT NULL` (no foreign key), `issuer text NOT NULL`, `subject text NOT NULL`,
`provider_id text NOT NULL`, `groups text[] NOT NULL DEFAULT '{}' CHECK (cardinality(groups) <= 500)`, `created_at timestamptz
NOT NULL DEFAULT now()`, `expires_at timestamptz NOT NULL CHECK (expires_at > created_at)`, `last_seen_at timestamptz NOT NULL
DEFAULT now()`, `revoked_at timestamptz`. No token, claim other than `groups`, or Paperclip content is stored.

**`collab_edge_handoffs`**: `code_hash bytea PRIMARY KEY CHECK (length(code_hash) = 32)`, `team_id text NOT NULL`, `host text NOT
NULL`, `issuer`, `subject`, `provider_id`, `groups` as above (the identity from the apex callback), `expires_at timestamptz NOT
NULL` (60 seconds after creation), `consumed_at timestamptz`, `created_at timestamptz NOT NULL DEFAULT now()`.

Functions (`afs_edge` only; each answers no row rather than an error for an unknown, expired, revoked or consumed value):

| Function | Contract |
|---|---|
| `afs.collab_handoff_create(p_code_hash bytea, p_team_id text, p_host text, p_issuer text, p_subject text, p_provider_id text, p_groups text[]) → timestamptz` | Called by the apex callback after the OIDC exchange. Stores the identity under the code's hash and returns `expires_at` (`now() + 60 s`). `23505` if the hash exists |
| `afs.collab_handoff_consume(p_code_hash bytea, p_host text, p_session_id_hash bytea) → (team_id text, expires_at timestamptz)` | Atomically `UPDATE … SET consumed_at = now() WHERE code_hash = $1 AND host = $2 AND consumed_at IS NULL AND expires_at > now() RETURNING`, and in the same statement's transaction inserts a session row for that identity with the hash the edge generated and `expires_at = now() + collab.session_ttl_minutes`. Single use across replicas; the edge sets the cookie from its own random id, so the plain id is never in the database. No row when the code is unknown, expired, consumed or for another host |
| `afs.collab_session_get(p_id_hash bytea) → (team_id text, issuer text, subject text, provider_id text, groups text[], expires_at timestamptz, last_seen_at timestamptz)` | One row for a live session (not expired, not revoked); sets `last_seen_at` at most once a minute. The edge calls `collab_principal` with these `groups` and caches the decision at most 60 s per session. The edge checks `team_id` against the request's team and refuses a session when the team's web UI is not effective (route check); no row is deleted for that |
| `afs.collab_session_revoke(p_id_hash bytea) → boolean` | Sign-out: sets `revoked_at`; true when a live session was revoked |

The reconciler calls `afs.purge_collab_edge_sessions() → bigint` hourly: deletes sessions expired or revoked more than an hour
ago and handoffs expired more than an hour ago; returns the rows deleted.

### 7.2.9 Swarm templates with a collaboration agent (G10, PC-D29; P1, milestone C4)

A swarm template `spec` gains an optional `collaboration: {templateId}` (an agent template `tpl_…` that has the `paperclip`
capability). `afs.instantiate_work_order_team` (000016) is extended: when the spec has it, the function also inserts, in the same
transaction, the team's collaboration agent (`role = 'collaboration'`, that template and its current digest, a dedicated identity,
daily snapshots, name `paperclip`; its model is the swarm's first pool's, and its image is that pool's repository at the collaboration template's current digest, unless the spec's `collaboration` gives an `image`; `agent_templates` has no model or repository column: `-db` decision DB-D18; no pool raises `23514`) and its `team_collaboration` row (web UI on,
REST API off, `registration_mode = 'manual'`), and writes the outbox events `agent.created` (API contract §7 envelope) beside the
existing ones. An unknown or disabled template, or one without `paperclip`, raises `23514` and creates nothing. `afs-api` is not
in this flow, so the three boot secrets are generated by the reconciler (it creates each secret in Secrets Manager with a random
value, as in `CreateAgent`) and recorded with `afs.record_work_order_secret`, which now also accepts the id of the work order
team's collaboration agent (`agt_…`) in its pool argument: it then records an agent-scope secret with `managed_by = 'afs'` and its
binding, only for the three boot secret names and their environment variables (`BETTER_AUTH_SECRET`,
`PAPERCLIP_TOOL_ACTION_SIGNING_SECRET`, `PAPERCLIP_SECRETS_MASTER_KEY`); other rules as for a pool secret.

### 7.2.10 Migration 000021 and notes from the build of 000020 (contract v1.3.2)

**000021, provider client ids.** `afs.collab_routes()` additionally returns `provider_client_id` (the team provider's console client id, `identity_providers.client_id`) and `provider_cli_client_id` (its CLI client id, `cli_client_id`), appended after `collab_client_secret_arn`. `afs-edge` uses them to accept REST bearer tokens minted for the console or CLI client (API contract §4.4c, "Bearer audiences"). The ids are public OIDC client ids, not secrets. `afs_edge` still reads no table. The function is dropped and created again because its return type changes; the grant to `afs_edge` is repeated. No table is touched.

**Facts about 000020 that consumers rely on:**

- **Change feed payload.** `team_collaboration` and `agent_collaboration` have no `id` column, so their `afs_desired_state` notification is `<table>:<team_id>:` with an empty id part. Listeners key on the team.
- **Revision key.** `config_revisions.resource_id` for `team_collaboration` is the `team_id` (one row per team, whatever agent it points at). `agent_collaboration` uses the usual `team_id/agent_id` composite form.
- **Edge session tables.** `collab_edge_sessions` and `collab_edge_handoffs` have row-level security enabled with a `deny_all` policy (`USING (false)`) for `afs_app`; no role holds a grant. Only the `afs_edge` functions of §7.2.8 reach them.
- **Partition helpers.** `EXECUTE` on `ensure_usage_partition`, `ensure_activity_partition` and `ensure_traffic_partition` is revoked from `PUBLIC` (they are `SECURITY DEFINER` and `afs_edge` must not reach them); `afs_reconciler` keeps its explicit grants.
- **Team group bindings.** A group binding on a team (`team_id` set) carries no provider (000010). `afs.collab_principal` resolves it against the team's identity provider, else the default one; only a service-level binding names its own provider.

### 7.2.7 Change feed, RLS and tests

- Change feed (D30): notify triggers on `team_collaboration` and `agent_collaboration` (payloads with an empty id part, DB-D2); `teams`, `agents`, and
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
  writes no other type), `TestCollaborationAccess/*` (alignment, additive upsert, retention), `TestHostnameHold/*`, `TestEdgeSessions/*` (single-use handoff under concurrency, expiry, revoke, host binding),
  `TestCollabKeyFunctions/*` and `TestSwarmCollaboration/*`, and up/down/up with checksums.

## 7.3 Migration 000022: team orchestration agent and model access (contract v1.4.0)

Requirements: [team orchestration agent PRD](../../team-orchestration-agent-PRD.md) ORC-1 to ORC-19, ORC-28, ORC-31,
MOD-1 to MOD-7 and section 8 (M1); stories DB-US-58 to DB-US-61; decisions OR-D1 to OR-D17 (approved by J, 2026-11-23).
Minor release **1.1.0**, lockstep with `-restapi` 1.1.0. One transaction; additive except where a row is renamed or
backfilled, as listed. `.down.sql` reverses it for local use and tests (the boolean and `collaboration` mappings are
lossless, M1). Contract decisions taken here are CD-13 to CD-25 (§9). The migration header notes the lock impact of
each statement, as summarised in §7.3.12.

What stays until 2.0.0 and is kept in step by triggers: `team_collaboration.web_ui_enabled` and `rest_api_enabled`,
`teams.may_expose_collaboration`, `agents.model_id` and `agent_pools.model_id`, `team_models.inference_profile_arn`,
`afs.collab_routes()`, the settings `collab.base_domain` and `collab.public_endpoints` (as read-only aliases), and the
capability value `paperclip` (rewritten on write). 2.0.0 drops them (PRD M6).

**Pre-flight.** None beyond 000021: no new role is needed.

### 7.3.1 Role rename and the one-per-team rule (DB-US-58)

| Change | Definition | Lock and notes |
|---|---|---|
| Rename | `UPDATE afs.agents SET role = 'orchestration' WHERE role = 'collaboration'` with the triggers `agents_collaboration_guard`, `agents_touch`, `agents_revision` and `agents_notify` disabled for the statement (`ALTER TABLE … DISABLE TRIGGER`, owner only, re-enabled before the next statement), so `version`, ETags and revisions do not change (CD-22) | Row locks on the few converted agents |
| `agents_role_check` | Replaced (`NOT VALID` then `VALIDATE`): `CHECK (role IN ('worker','orchestration'))` | `SHARE UPDATE EXCLUSIVE` while validating |
| Index | `agents_team_collaboration_uq` dropped; `CREATE UNIQUE INDEX agents_team_orchestration_uq ON afs.agents (team_id) WHERE role = 'orchestration' AND deleted_at IS NULL`. A second live orchestration agent → `23505` | Plain build, `SHARE` lock for milliseconds (as 000020) |
| `afs.agents_collaboration_guard()` | Replaced by `afs.agents_orchestration_guard()` (same trigger point, `BEFORE INSERT OR UPDATE OF role, name, template_id, iam_identity, snapshot_schedule`): role change → `23514` (`agents_role_immutable`, as today); `INSERT` with `role = 'orchestration'` while `current_user = 'afs_app'` → `23514` (`agents_role_reserved`), so only the `SECURITY DEFINER` functions of §7.3.7 create one; `role = 'orchestration'` needs a template whose `capabilities` contain `orchestration` (`agents_orchestration_capability`), `iam_identity = 'dedicated'` (`agents_orchestration_identity`) and `snapshot_schedule <> 'off'` (`agents_orchestration_snapshots`); `role = 'worker'` on an `orchestration` template → `23514` (`agents_worker_capability`) | Messages name the failed rule |
| Reserved name | Same guard: `INSERT` of an agent named `orchestrator` with `role <> 'orchestration'` → `23514` (`agents_name_reserved`). A trigger on `agent_pools` (`BEFORE INSERT`) refuses a pool named `orchestrator` the same way (`agent_pools_name_reserved`), because agent and pool names share a namespace. Names are immutable, so only inserts are checked; a 1.0.1 worker or pool already named `orchestrator` keeps its name (CD-19) | |
| Delete guard | Trigger `afs.agents_orchestration_required()` (`BEFORE UPDATE OF state, deleted_at`): an orchestration agent moving to `state IN ('deleting','deleted')` or getting `deleted_at` while its team's `state` is not `deleting` or `deleted` → `23514` (constraint name `agents_orchestration_required`) | |
| Functions that named `'collaboration'` | Replaced to name `'orchestration'`, with no other change: `afs.agent_templates_capability_guard()` (now on the `orchestration` capability), `afs.agents_collaboration_cleanup()` and its trigger's `WHEN (NEW.role = 'orchestration')`, `afs.team_collaboration_guard()`, the hostname-hold trigger function on `teams` (any `agents` row with `role = 'orchestration'`, deleted ones included), `afs.record_work_order_secret`, `afs.record_collab_board_key`, `afs.collab_routes()` (§7.3.6). A test greps `pg_proc.prosrc` for the literal `'collaboration'` used as a role value and finds none | `CREATE OR REPLACE`, no table lock |
| `teams.orchestration_required` | `boolean NOT NULL DEFAULT false`, then `ALTER COLUMN … SET DEFAULT true`: existing teams `false`, new teams `true`. Constraint trigger `teams_orchestration_required` (`AFTER INSERT OR UPDATE OF orchestration_required`, `DEFERRABLE INITIALLY DEFERRED`): at commit, a team with `orchestration_required` that is not `deleting` or `deleted` and has no live orchestration agent → `23514`. Only `afs_app` with `afs.caller_is_service_admin()` and the functions of §7.3.7 may set it (`42501` otherwise; added to `teams_guardrail_guard`'s column list) | Constant defaults, no rewrite |

`afs-api` never deletes the orchestration agent: `DeleteTeam` moves the team to `deleting`, and the reconciler then marks
the workers, then the orchestration agent, `deleting` and `deleted` (TEAM-9), which the delete guard allows.

### 7.3.2 Tool, exposure levels and the limit (DB-US-59)

| Change | Definition | Lock and notes |
|---|---|---|
| `team_collaboration.tool` | `text NOT NULL DEFAULT 'paperclip' CHECK (tool IN ('paperclip','buzz'))`. Adding a tool is a later migration (text plus CHECK) | Constant default |
| `team_collaboration.web_ui_exposure`, `web_api_exposure` | `text NOT NULL DEFAULT 'off' CHECK (… IN ('off','private','public'))`; backfilled in the migration from the booleans (`true` → `public`, `false` → `off`) with the touch, revision and notify triggers disabled (CD-22) | Updates every row of a small table |
| Booleans kept in step | Trigger `afs.team_collaboration_levels_sync()` (`BEFORE INSERT OR UPDATE`), until 2.0.0 (CD-16). **Insert:** the levels win and the booleans are derived (`enabled := exposure <> 'off'`). **Update:** if a level changed, the matching boolean is derived from it; else if a boolean changed, its level becomes `off` for `false` and, for `true`, the team's `max_collaboration_exposure` when the tool supports the surface (else `off`, which reads back `false`). A statement that changes both a level and its boolean inconsistently → the level wins | |
| `teams.max_collaboration_exposure` | `text NOT NULL DEFAULT 'off' CHECK (… IN ('off','private','public'))`; backfilled from `may_expose_collaboration` (`true` → `public`, `false` → `off`) with the touch, revision and notify triggers disabled. Added to `teams_guardrail_guard` (only service admins, `42501`). `afs-api` always passes it on insert, from `CreateTeam` or `orchestration.default_limit` | The backfill updates every team row; `teams` holds hundreds of rows |
| `may_expose_collaboration` kept in step | Trigger on `teams` (`BEFORE INSERT OR UPDATE`): insert, the limit wins (`may := limit <> 'off'`); update, a changed limit sets `may`, else a changed `may` sets the limit (`true` → `public`, `false` → `off`), as ORC-27 | |
| Exposure check | Trigger `afs.team_collaboration_exposure_check()` (`BEFORE INSERT OR UPDATE OF web_ui_exposure, web_api_exposure, tool, registration_mode`, after the sync trigger). For each surface whose level is new (insert) or changed, or every surface when `tool` changed (CD-15): a level above `teams.max_collaboration_exposure` (order `off` < `private` < `public`) → `23514` (`team_collaboration_exposure_limit`); a level above `off` for a surface the tool's profile does not support → `23514` (`team_collaboration_surface_supported`). `registration_mode` not in the tool's `registration` list → `23514` (`team_collaboration_registration_supported`). The profile is read from `orchestration.tools` (§7.3.4), whose CHECK fixes it per tool: Paperclip supports both surfaces and `manual`, `managed`; Buzz supports neither surface and `managed` only. A stored level above a later-lowered limit is never re-checked, so lowering the limit keeps the team's choice (ORC-14) | |
| Tool and template | Constraint trigger `team_collaboration_tool_template` (`AFTER INSERT OR UPDATE OF tool, agent_id` on `team_collaboration` and `AFTER UPDATE OF template_id` on orchestration agents; `DEFERRABLE INITIALLY DEFERRED`): at commit the agent's template must carry `tool:<tool>` → else `23514`. Deferred so `ChangeCollaborationTool` may update the row and the agent in either order | |
| Generation | `afs.team_collaboration_generation()` replaced: also bumps `generation` when `tool`, `web_ui_exposure` or `web_api_exposure` changes | |
| Grants | `afs_app`: `UPDATE (tool, web_ui_exposure, web_api_exposure, web_ui_enabled, rest_api_enabled, registration_mode)`; the `INSERT` grant is **revoked** (the row is created only by §7.3.7); `afs_reconciler`, `afs_readonly`: `SELECT` as today | |
| Snapshots | `agent_volume_snapshots.reason` CHECK replaced (`NOT VALID` then `VALIDATE`) to add `pre_tool_change`; new nullable columns `tool text CHECK (tool IN ('paperclip','buzz'))` (the tool the volume held) and `retain_until timestamptz`. `CHECK (reason <> 'pre_tool_change' OR (tool IS NOT NULL AND retain_until IS NOT NULL))`. `afs-api` inserts the `requested` row in the `ChangeCollaborationTool` transaction with `retain_until = now() + 90 days`; the reconciler never prunes a snapshot before its `retain_until` (CD-23) | Nullable columns, no rewrite |
| `collaboration_access.exposure` | `text NOT NULL DEFAULT 'public' CHECK (exposure IN ('public','private'))`; the primary key is dropped and re-created with `exposure` after `surface` (ORC-31) | `ACCESS EXCLUSIVE` on the partitioned table while the index rebuilds; the table holds at most weeks of 1.0.1 counts. Run during the upgrade window |

### 7.3.3 Template capabilities

| Change | Definition |
|---|---|
| `afs.capabilities_ok(text[])` | Replaced: known values `orchestration`, `tool:paperclip`, `tool:buzz` (and nothing else); at most 8, no duplicates, as before. Additionally a template with `orchestration` has exactly one `tool:*` value, and a `tool:*` value needs `orchestration` |
| Rewrite | Existing `paperclip` values become `{orchestration, tool:paperclip}` in the migration (constraint dropped, rows updated with the touch, revision and notify triggers disabled, constraint re-added `NOT VALID` then `VALIDATE`). Until 2.0.0 a `BEFORE INSERT OR UPDATE OF capabilities` trigger rewrites a written `paperclip` the same way, so a 1.0.1 `PutAgentTemplate` keeps working (CD-24) |
| Guard | `afs.agent_templates_capability_guard()` also refuses (`55000`) removing a `tool:*` value or `orchestration` while a live orchestration agent uses the template, or while `orchestration.tools` names the template for that tool |

### 7.3.4 Settings (`orchestration.*`, `models.*`)

New constraint `service_settings_orchestration_check` and `service_settings_models_check` (`NOT VALID` then
`VALIDATE`), plus a `BEFORE INSERT OR UPDATE` trigger on `service_settings` for checks that read other tables. Values and
seeds (rows inserted `ON CONFLICT (key) DO NOTHING`):

| Key | Shape and range | Seed in 000022 |
|---|---|---|
| `orchestration.tools` | JSON object with exactly the keys `paperclip` and `buzz`; each `{enabled: boolean, default: boolean, templateId: "tpl_…"\|null, imageRepository: string\|null, webUi: boolean, webApi: boolean, registration: [..], inNamespacePort: integer}`. The profile members are fixed: `paperclip` `webUi true, webApi true, registration ["manual","managed"], inNamespacePort 3100`; `buzz` `false, false, ["managed"], 3000`. Exactly one `default`, and it is `enabled`. `imageRepository` is an OCI repository without tag or digest (`^[a-z0-9.-]+(:[0-9]+)?(/[a-z0-9._-]+)+$`). The trigger checks that a non-null `templateId` names an existing template whose capabilities contain `orchestration` and `tool:<key>` (`23514`, `orchestration_tools_template`) (CD-17) | `paperclip`: enabled, default; `templateId` = the one enabled template with `paperclip` before the rewrite when exactly one exists, else `null`; `imageRepository` = the repository part (before `@`) of the newest live collaboration agent's `image`, else `null`. `buzz`: disabled, `templateId` and `imageRepository` `null` |
| `orchestration.public_base_domain` | as `collab.base_domain` (`null` or DNS name) | copy of `collab.base_domain` |
| `orchestration.private_base_domain` | as above | `null` |
| `orchestration.public_endpoints` | boolean | copy of `collab.public_endpoints` |
| `orchestration.private_endpoints` | boolean | `true` |
| `orchestration.default_limit` | `"off"`, `"private"`, `"public"` | `"public"` when `collab.base_domain` is set (and, at migration time, `private_base_domain` is always unset), else `"private"` (OR-D5) |
| `orchestration.default_web_ui_exposure` | same values, not above `default_limit` (the trigger checks both keys on either write, `23514`) | same rule as `default_limit` |
| `orchestration.default_web_api_exposure` | same values, not above `default_limit` | `"off"` |
| `orchestration.default_resources` | object `{cpu, memory}` as `agents.resources` | `{"cpu": "1", "memory": "4Gi"}` |
| `orchestration.default_volume_gib` | integer 10 to 1000 | `20` |
| `models.service_access` | `"all"`, `"selected"` | `"selected"` when `afs.models` has at least one row at migration time (an upgraded environment keeps 1.0.1 behaviour), else `"all"` (CD-18, OR-D15, DB-US-61) |
| `models.default_team_access` | `"all"`, `"selected"` | `"all"` |
| `models.default_team_models` | JSON array of at most 100 distinct model ids, each an existing `models.id` (trigger) | `[]` |
| `models.default_model_id` | `null` or an existing `models.id` (trigger) | `null` (CD-18: there is no 1.0.1 "service default model" to copy; `afs-api` falls back as API contract §4.4d says) |

**Aliases (CD-25).** A write of `orchestration.public_base_domain` or `orchestration.public_endpoints` also writes
`collab.base_domain` or `collab.public_endpoints` to the same value (same trigger). A direct write of either `collab.*`
key by `afs_app` → `23514` (`service_settings_alias_read_only`); `afs_owner` (the trigger) is exempt. The other five
`collab.*` keys are unchanged and still writable. `afs.collab_settings()` keeps returning the seven `collab.*` keys;
the new `afs.orchestration_settings()` (§7.3.6) returns the `orchestration.*` keys except `orchestration.tools`
members `templateId` and `imageRepository`, which the edge does not need.

### 7.3.5 Model access (DB-US-61)

| Change | Definition | Lock and notes |
|---|---|---|
| `teams.model_access` | `text NOT NULL DEFAULT 'selected' CHECK (model_access IN ('all','selected'))`, then `SET DEFAULT 'all'`: existing teams `selected` (they have explicit `team_models` rows), new teams `all`. Added to `teams_guardrail_guard` (service admins only, `42501`, OR-D16) | Constant default |
| `team_models` | Unchanged in shape. It is the team's **selection**, read only while `model_access = 'selected'`; rows are kept when the team moves to `all`, so moving back restores the list. Its restrictive service-admin policies stay | |
| FKs to `team_models` | `agents (team_id, model_id) → team_models` and `agent_pools (team_id, model_id) → team_models` are dropped (CD-14): with `all` a team has no rows, and narrowing a team must not edit or block an agent (MOD-6). The FK of `model_id` to `models (id)` stays | Drop is instant |
| `agents.model_access`, `agent_pools.model_access` | `text NOT NULL DEFAULT 'all' CHECK (… IN ('all','selected'))`; existing rows `all` (what the 1.0.1 gateway already allowed, OR-D15) | Constant default |
| `agents.default_model_id`, `agent_pools.default_model_id` | `text REFERENCES afs.models (id)`; backfilled from `model_id` (triggers disabled, CD-22); then `CHECK (default_model_id IS NOT NULL)` `NOT VALID` then `VALIDATE`. Sync trigger until 2.0.0: insert, `default_model_id := coalesce(default_model_id, model_id)` and `model_id := default_model_id`; update, a changed `default_model_id` sets `model_id`, else a changed `model_id` sets `default_model_id` | Backfill touches every agent and pool row (thousands) in one statement |
| `agent_models` | `team_id text NOT NULL`, `agent_id text NOT NULL`, `model_id text NOT NULL REFERENCES afs.models (id)`, `created_at timestamptz NOT NULL DEFAULT now()`, `created_by text NOT NULL DEFAULT afs.current_actor()`; `PRIMARY KEY (team_id, agent_id, model_id)`; `FOREIGN KEY (team_id, agent_id) REFERENCES afs.agents (team_id, id) ON DELETE CASCADE`. At most 50 rows per agent (`23514`) | New table |
| `pool_models` | Same with `pool_id` and `FOREIGN KEY (team_id, pool_id) REFERENCES afs.agent_pools (team_id, id) ON DELETE CASCADE` | New table |
| Selection rules | `BEFORE INSERT` on `agent_models` and `pool_models`: the model must be enabled for the service (`23514`, `agent_models_service`) and allowed for the team (`23514`, `agent_models_team`) at write time. Constraint trigger `agents_models_check` (`AFTER INSERT OR UPDATE OF model_access, default_model_id` on `agents` and `AFTER INSERT OR DELETE` on `agent_models`, `DEFERRABLE INITIALLY DEFERRED`; the same on pools): at commit, for each agent whose model fields changed in the transaction, `selected` needs at least one row (`23514`, `agents_models_selection_nonempty`) and the default model must be in the stored selection (when `selected`) and enabled for the service and allowed for the team (`23514`, `agents_default_model_allowed`). A price is not required at write time (CD-14) | |
| `afs.team_inference_profiles` | `team_id text NOT NULL REFERENCES afs.teams (id) ON DELETE CASCADE`, `model_id text NOT NULL REFERENCES afs.models (id)`, `inference_profile_arn text CHECK (inference_profile_arn ~ '^arn:aws[a-z-]*:bedrock:[a-z0-9-]+:[0-9]{12}:application-inference-profile/[a-z0-9]+$')`, `state text NOT NULL DEFAULT 'creating' CHECK (state IN ('creating','active','retiring'))`, `retire_after timestamptz` (`CHECK ((state = 'retiring') = (retire_after IS NOT NULL))`), `created_at`, `updated_at`; `PRIMARY KEY (team_id, model_id)`. Written by the reconciler only; one row per model callable for the team, `retiring` for 7 days after it stops (MOD-2). Backfilled from `team_models.inference_profile_arn IS NOT NULL` as `active`. Until 2.0.0 a trigger copies the ARN into the matching `team_models` row when one exists, so 1.0.1 readers keep working (CD-13) | New table |
| `models` | New columns `origin text NOT NULL DEFAULT 'manual' CHECK (origin IN ('manual','bedrock_sync'))` and `synced_at timestamptz`. The reconciler's daily sync inserts new models with `origin = 'bedrock_sync'` and `enabled = false` (with `all` the flag is ignored; in `selected` new models start disabled, MOD-1). A change of `enabled` by `afs_app` while `models.service_access = 'all'` → `55000` (`models_enabled_fixed`) | Constant default |
| `afs.effective_agent_models` | View `WITH (security_invoker = true)` so the caller's RLS applies: one row `(team_id, subject_kind ('agent'\|'pool'), subject_id, model_id, is_default boolean)` per live agent or pool of a team that is not `deleted` and per model in **service ∩ team ∩ subject ∩ callable**. Service: every model when `models.service_access = 'all'`, else `models.enabled`. Team: service set when `model_access = 'all'`, else ∩ `team_models`. Subject: team set when `model_access = 'all'`, else ∩ `agent_models` / `pool_models`. Callable: a `model_prices` row with `effective_from <= now()` exists | |
| `afs.model_admission(p_subject_kind text, p_subject_id text)` | `STABLE`, `SECURITY INVOKER`, returns `(model_id text, reason text)` for every catalog model: `reason` NULL when admitted, else the first failed level in the order `model_not_enabled_for_service`, `model_not_enabled_for_team`, `model_not_enabled_for_agent` (also for a pool), `model_not_priced`. The gateway caches its result per subject (gateway contract §2.1) | |
| Grants and RLS | `agent_models`, `pool_models`: RLS `app_team_scope` and `service_roles_all`; `afs_app` `SELECT, INSERT, DELETE`; `afs_reconciler`, `afs_gateway`, `afs_readonly` `SELECT`. `team_inference_profiles`: RLS as other team tables with a `SELECT`-only policy for `afs_app`; `afs_reconciler` `SELECT, INSERT, UPDATE, DELETE`; `afs_gateway`, `afs_billing`, `afs_readonly` `SELECT`. The view and `afs.model_admission`: `SELECT`/`EXECUTE` to `afs_app`, `afs_reconciler`, `afs_gateway`, `afs_readonly`. `afs_reconciler` gains `INSERT (id, provider, display_name, enabled, context_window, max_output_tokens, origin, synced_at)` and `UPDATE (synced_at)` on `models`. `afs_gateway` gains `SELECT` on `agent_models`, `pool_models` and `team_inference_profiles` and `SELECT (key, value)` on `service_settings`, because the view runs with the caller's rights and reads `models.service_access` (no setting holds a secret) | |
| Change feed and revisions | `agent_models` and `pool_models` get revision triggers (keys `<team_id>/<agent_id>/<model_id>` and `<team_id>/<pool_id>/<model_id>`, explicit cases in `afs.record_revision()`) and notify triggers (payload `agent_models:<team_id>:` and `pool_models:<team_id>:`, empty id part as DB-D2). `team_inference_profiles` and `model_prices` get notify triggers only. `service_settings` gets a notify trigger for keys `models.%` and `orchestration.%` (payload `service_settings::<key>`). `teams`, `agents`, `agent_pools`, `models` and `team_models` already notify. Every input of the view therefore notifies (DB-US-61) | |
| `seedOtherTeams` | Gains rows in `agent_models`, `pool_models` and `team_inference_profiles` (the last read-only for `afs_app`) | |

### 7.3.6 Edge functions (DB-US-60)

`afs_edge` gains `EXECUTE` on `afs.orchestration_routes()` and `afs.orchestration_settings()` (now **twelve** functions plus
`afs.schema_version()`); still no table privilege.

**`afs.orchestration_routes()`** returns **two rows per team** (surfaces `web_ui` and `web_api`) for each team that is not
`deleting` or `deleted` and has a `team_collaboration` row:

| Column | Type | Meaning |
|---|---|---|
| `team_id`, `slug`, `namespace`, `team_state` | `text` | as `collab_routes()` |
| `agent_id`, `agent_state` | `text` | the orchestration agent |
| `tool` | `text` | `paperclip` or `buzz` |
| `service_name`, `port` | `text`, `integer` | the tool's in-namespace Service (`paperclip`, `buzz`) and `inNamespacePort` |
| `surface` | `text` | `web_ui` or `web_api` (CD-20) |
| `supported` | `boolean` | the tool's profile has the surface |
| `exposure` | `text` | stored choice |
| `limit_exposure` | `text` | `teams.max_collaboration_exposure` |
| `effective` | `text` | `off`, `private` or `public`, computed below |
| `reasons` | `text[]` | every condition that lowered `exposure` to `effective`: `tool_not_supported`, `team_limit`, `service_switch_public`, `service_switch_private`, `base_domain_unset`, `provider_without_collab_client` (web UI only, as 1.0.1). Empty when `effective = exposure` |
| `public_hostname`, `private_hostname` | `text` | `slug || '.' || <base domain>`, NULL while that base domain is unset (both returned so the edge can answer a wrong-level host with `404`) |
| `hostname` | `text` | the hostname of `effective`, NULL when `off` |
| `ready`, `not_ready_reason` | `boolean`, `text` | as `collab_routes()` |
| `provider_id`, `issuer_url`, `groups_claim`, `collab_client_id`, `collab_client_secret_arn`, `provider_client_id`, `provider_cli_client_id` | `text` | as `collab_routes()` (000021) |

Effective level: start from `exposure`; `off` if the tool does not support the surface (`tool_not_supported`); then
`min(level, limit)` (`team_limit` when it lowered); then `public` → `off` when `orchestration.public_endpoints` is false
(`service_switch_public`) or `orchestration.public_base_domain` is unset (`base_domain_unset`); `private` → `off` when
`orchestration.private_endpoints` is false (`service_switch_private`) or `orchestration.private_base_domain` is unset
(`base_domain_unset`); for `web_ui`, `off` when the provider has no `collab_client_id`. A lowered level never falls to the
other non-off level: a public choice capped by a `private` limit is `private`, but a public surface under the public kill
switch is `off`, not `private`.

**`afs.collab_routes()`** stays for the 1.0.1 edge during a rolling upgrade and is recomputed from the new columns: one row
per team as before, `web_ui_enabled`/`rest_api_enabled` are the booleans, `web_ui_effective`/`rest_api_effective` are
`effective = 'public'` of the matching surface, `may_expose` is `limit <> 'off'`, `hostname` uses
`orchestration.public_base_domain`, and `service_name`, `port` follow the tool. Dropped in 2.0.0.

**`afs.orchestration_settings()`** returns `(key text, value jsonb)` for `orchestration.public_base_domain`,
`orchestration.private_base_domain`, `orchestration.public_endpoints` and `orchestration.private_endpoints`.

**`afs.record_collab_access(p_rows jsonb)`** accepts an optional `exposure` member (`public` or `private`; absent means
`public`, which is what a 1.0.1 edge sends; anything else `23514`) and a `surface` of `web_ui`, `rest_api` or `web_api`
(`web_api` is stored as `rest_api`, CD-20). Same limits and return value as 000020.

### 7.3.7 Creating the orchestration agent

**`afs.create_orchestration_agent(p_team_id text, p_agent_id text, p_name text, p_tool text, p_web_ui_exposure text,
p_web_api_exposure text, p_registration_mode text, p_model_access text, p_model_ids text[], p_default_model_id text,
p_resources jsonb, p_storage_size_gib integer, p_storage_on_delete text) → text`**: `SECURITY DEFINER`, owned by
`afs_owner`, `SET search_path = pg_catalog, afs`, `EXECUTE` for `afs_app` only. Used by `CreateTeam` (in its transaction,
after the team row) and by the backfill (RA-US-21). It:

1. Requires `afs.caller_is_service_admin()` (`42501`); the team to exist and not be `deleting` or `deleted` (`55000`);
   `p_agent_id` to be an `agt_` ULID (the API generates it first, because the boot secret paths derive from the agent).
2. Reads `orchestration.tools`: `p_tool` not `enabled` → `23514` (`orchestration_tool_not_enabled`); its `templateId` or
   `imageRepository` `null`, or the template disabled → `55000` (`orchestration_runtime_unset`).
3. Inserts the agent: `role = 'orchestration'`, `name = coalesce(p_name, 'orchestrator')`, the tool's template
   (`template_id`, `template = harness`), `image = imageRepository || '@' || current_image_digest`, `iam_identity =
   'dedicated'`, `snapshot_schedule = 'daily'`, `snapshot_retain_count = 14`, `storage_on_delete =
   coalesce(p_storage_on_delete, 'snapshot_then_delete')`, `storage_size_gib = coalesce(p_storage_size_gib,
   orchestration.default_volume_gib)`, `resources = coalesce(p_resources, orchestration.default_resources)`,
   `model_access`, `default_model_id` and the `agent_models` rows from the model arguments. A second live orchestration
   agent → `23505` (`agents_team_orchestration_uq`).
4. Inserts `team_collaboration` (`tool`, both levels, `registration_mode`, default `manual` for Paperclip and `managed`
   for Buzz); the checks of §7.3.2 apply.
5. Sets `teams.orchestration_required = true` (a no-op for new teams; the backfill relies on it).
6. Writes one `audit_log` row (`CreateOrchestrationAgent`, actor `afs.current_actor()`, `after` without secrets) and the
   outbox events `agent.created` and `orchestration.created` with the API contract §7 envelope (`afs.event_detail`)
   (CD-21). Returns the agent id.

The boot secret rows (`managed_by = 'afs'`) and their bindings are inserted by `afs-api` after the call, in the same
transaction, as 000020 allows. The backfill passes `p_name = 'orchestrator'`, or `team-orchestrator` when a live worker
or pool of the team already holds `orchestrator` (CD-19); actor `system:migration` with `afs.service_admin = 'on'`.

**`afs.instantiate_work_order_team(work_order_id)`** is replaced: the swarm template's optional `spec.collaboration`
(PC-D29) is superseded by optional `spec.orchestration {tool?, webUiExposure?, webApiExposure?, defaultModelId?}`
(defaults: the service default tool, `orchestration.default_web_*_exposure` capped by the team limit, which is
`orchestration.default_limit`). It always calls the logic of `create_orchestration_agent` (as owner, so the
`afs_app` grant does not apply) with `storage_on_delete = 'delete'` (ORC-7, OR-D12), `model_access = 'all'` and
`defaultModelId` defaulting to the first pool's model. The work order team itself is `model_access = 'selected'` with the
pools' models, as today. A template whose spec still has `collaboration {templateId}` is accepted until 2.0.0 and read as
`orchestration {tool: 'paperclip'}`; the `templateId` is ignored in favour of `orchestration.tools`. If the tool's runtime
is unset the function raises `55000` and creates nothing (the work order stays `open`, as for other instantiation
failures). `afs.record_work_order_secret` accepts the work order team's orchestration agent id as before (000020),
for the tool's boot secret names.

### 7.3.8 Reserved secret names for Buzz (ORC-10)

`secrets.managed_by` CHECK gains `buzz` (`'user','afs','paperclip','buzz'`), and `afs.secrets_managed_guard()` is
replaced: the name `buzz` is refused (`23514`); `buzz-agent-private-key` is `managed_by = 'afs'` only, agent scope, on a
worker of a team whose tool is `buzz` (no manual mode); other `buzz-*` names are `managed_by = 'buzz'`, agent scope, on the
orchestration agent, with the ARN under `afs.secret_path(team_id, agent_id, 'buzz') || '/'` and `origin = 'registered'`,
exactly as the `paperclip` rules of §7.2.4 (name derivation, the partial unique index widened to
`managed_by IN ('paperclip','buzz')`, the reconciler-only write rule). `afs.record_collab_agent_key` and
`afs.remove_collab_agent_key` accept the Buzz key: in a Buzz team they write `buzz-agent-private-key` bound as
`BUZZ_PRIVATE_KEY` instead of the Paperclip key. Buzz content and keys are never stored in the database.

### 7.3.9 Error mapping (additions to §6)

`-restapi` maps by constraint name, including errors returned by `COMMIT` for the deferred triggers.

| SQLSTATE | Constraint or source | API code | `details.reason` |
|---|---|---|---|
| `23514` | `agents_role_reserved`, `agents_role_check` (value `collaboration`) | `ValidationError` | `role_reserved` |
| `23514` | `agents_name_reserved`, `agent_pools_name_reserved` | `ValidationError` | `name_reserved` |
| `23514` | `agents_orchestration_required` | `409 Conflict` | `orchestration_agent_required` |
| `23505` | `agents_team_orchestration_uq` | `409 Conflict` | `orchestration_agent_exists` |
| `23514` | `team_collaboration_exposure_limit` | `ValidationError` | `exposure_above_limit` |
| `23514` | `team_collaboration_surface_supported` | `ValidationError` | `surface_not_supported_by_tool` |
| `23514` | `team_collaboration_registration_supported` | `ValidationError` | `registration_mode_not_supported` |
| `23514` | `orchestration_tool_not_enabled` | `ValidationError` | `tool_not_enabled` |
| `55000` | `orchestration_runtime_unset` | `409 Conflict` | `orchestration_runtime_unset` |
| `23514` | `agent_models_service`, `agent_models_team` | `ValidationError` | `model_not_enabled_for_service`, `model_not_enabled_for_team` |
| `23514` | `agents_models_selection_nonempty` | `ValidationError` | `models_selection_empty` |
| `23514` | `agents_default_model_allowed` | `ValidationError` | `default_model_not_allowed` |
| `55000` | `models_enabled_fixed` | `409 Conflict` | `service_model_access_all` |
| `23514` | `service_settings_alias_read_only` | `ValidationError` | `setting_renamed` |
| `23514` | `orchestration_tools_template`, `service_settings_orchestration_check`, `service_settings_models_check` | `ValidationError` | none (field `value`) |
| `23514` | `teams_orchestration_required`, `team_collaboration_tool_template` (deferred) | `InternalError` | none: `afs-api` broke an invariant; logged with the constraint name |

### 7.3.10 What each service touches (additions to §4)

| Object | api | reconciler | gateway | billing | edge |
|---|---|---|---|---|---|
| `team_collaboration` new columns | R, U(cols) | R | | | via functions |
| `teams.max_collaboration_exposure`, `model_access`, `orchestration_required` | R, W (guarded) | R | R | R | via functions |
| `agents.model_access`, `default_model_id`; `agent_pools` same | R, W | R | R | R | |
| `agent_models`, `pool_models` | R, I, D | R | R | | |
| `team_inference_profiles` | R | R, W | R | R | |
| `models.origin`, `synced_at` | R | R, I (sync) | R | R | |
| `afs.effective_agent_models`, `afs.model_admission` | R, F | R, F | R, F | | |
| `afs.create_orchestration_agent` | F | | | | |
| `afs.orchestration_routes`, `afs.orchestration_settings` | | | | | F |

### 7.3.11 Tests that prove each rule

- `TestOrchestrationAgent/*`: second live orchestration agent `23505`; team without one at commit `23514`; direct
  `afs_app` insert of `role = 'orchestration'` `23514`; delete guard (live team refused, `deleting` team allowed);
  reserved name for agents and pools; role migration of a seeded `collaboration` row with unchanged `version`; no
  function source names the `collaboration` role.
- `TestCreateOrchestrationAgent/*`: happy path writes agent, `team_collaboration`, `agent_models`, audit and both outbox
  rows; disabled tool `23514`; unset runtime `55000`; non-admin `42501`; `orchestration_required` set.
- `TestCollaborationExposure/*`: booleans and levels in step in both directions (including `true` under a `private` limit
  and under limit `off`); limit refusal; Buzz refusal for both surfaces and for `manual`; a stored level above a lowered
  limit survives an unrelated update; tool change re-checks both surfaces; deferred tool/template check.
- `TestServiceSettingRanges/orchestration.*` and `/models.*`: every range, exactly one default tool, template
  capability check, default levels not above the default limit, aliases read-only, OR-D5 and DB-US-61 seeds on an
  upgraded and on a fresh database.
- `TestEdgeRole/orchestration_routes`: the effective-level table for every combination of choice, limit, tool, kill
  switches, base domains and provider client; `collab_routes()` still matches 1.0.1 for 1.0.1 data; `afs_edge` reads no
  table; `record_collab_access` with and without `exposure`.
- `TestWorkOrderTeamHasOrchestrationAgent`: with and without `spec.orchestration`, legacy `spec.collaboration`,
  `storage_on_delete = 'delete'`, runtime unset leaves the work order `open`.
- `TestModelAccess/*`: each level's narrowing (service `selected`, team `selected`, agent and pool `selected`), the price
  rule, an empty selection, a default outside the set at write time, narrowing a team leaves `agent_models` unchanged,
  `model_admission` reason order, `enabled` fixed under `all`, sync insert grant.
- `TestManagedSecrets/buzz_*`, `TestToolChangeSnapshot/*`.
- `TestRowLevelSecurityIsolatesTeams/agent_models`, `/pool_models`, `/team_inference_profiles`;
  `TestCrossTeamWritesChangeNothing/agent_models`, `/pool_models`, `/team_collaboration`; up/down/up with checksums.

### 7.3.12 Lock impact summary

`agents`, `agent_pools`, `teams`, `team_collaboration`, `agent_templates`: constant-default columns (no rewrite), CHECKs
`NOT VALID` then `VALIDATE`, one plain unique index (`SHARE` for milliseconds), and backfill `UPDATE`s of every row of
`teams` (hundreds), `team_collaboration` (at most one per team), `agent_templates` (tens) and `agents`/`agent_pools`
(thousands, `default_model_id`) with triggers disabled. `collaboration_access`: primary key rebuilt under `ACCESS
EXCLUSIVE` (small). `service_settings`: two CHECKs and seeded rows. Functions and views: `CREATE OR REPLACE`. Expected
run time well under the 10 s `lock_timeout`; run it in the upgrade window that also runs the backfill hook.

## 7.4 Migration 000023: team model gateway, routes and provider switches (contract v1.5.0)

Source: [model endpoint gateway PRD](../../model-endpoint-gateway-PRD.md) §7, §9, §11 and Appendix D.2 (approved by J,
2026-11-25). Release `-db` 1.2.0 with `-restapi` 1.2.0. All objects in schema `afs`; ids are prefixed ULIDs
(`mep_`, `epp_`, `pst_`). Desired-state tables carry `version`, `created_at/by`, `updated_at`, the touch and revision
triggers and a notify trigger on `afs_desired_state` (payload `<table>:<team_id>:<id>`, empty team for service rows).

### 7.4.1 Providers

| Object | Definition |
|---|---|
| `inference_providers` | `provider text PRIMARY KEY CHECK (provider ~ '^[a-z][a-z0-9_]{1,30}$')`, `display_name text NOT NULL`, `hosts text[] NOT NULL DEFAULT '{}'` (FQDN globs, each `^(\*\.)?[a-z0-9.-]+$` or `*-aiplatform.googleapis.com` style; at most 20), `enabled boolean NOT NULL`, `team_selection text NOT NULL DEFAULT 'team_admin' CHECK (team_selection IN ('team_admin','service_admin'))`, `disabled_reason text` (≤ 500), `fallback_model text` (Bedrock only: `<route>/<model>` chosen when it was turned off), `version`, `changed_by`, `changed_at`. No `team_id`: service-wide. `afs_app` may `UPDATE (enabled, team_selection, disabled_reason, fallback_model)` only when `afs.service_admin` is set (`42501`); no insert or delete by `afs_app` except provider `other`-style rows added by service admins (`INSERT` with the same check) |
| Seed | `bedrock` (hosts `bedrock-runtime.*.amazonaws.com`), `openai` (`api.openai.com`), `openrouter` (`openrouter.ai`), `nous` (`inference-api.nousresearch.com`), `opencode` (`opencode.ai`): `enabled = true`, `team_admin`. `azure` (`*.openai.azure.com`, `*.services.ai.azure.com`, `*.cognitiveservices.azure.com`) and `google` (`aiplatform.googleapis.com`, `*-aiplatform.googleapis.com`): `enabled = false`, `service_admin`. `other` (no hosts: matches any external host not listed): `true`, `team_admin`. `internal` is not a row: `corporate` and `in_namespace` endpoints have no provider switch |
| `afs.provider_for_host(p_host text) RETURNS text` | `STABLE`; first provider whose `hosts` glob matches, else `'other'` |
| Bedrock-off guard | `BEFORE UPDATE` trigger: setting `bedrock.enabled = false` requires `models.default_model_id` to be a route model (`<route>/<model>`) whose endpoint is enabled, on an enabled provider, and selected for every team that is not `deleted`; else `23514` (`no_fallback_model`). `afs-api` performs the "select for every team" step in the same transaction before the update |

`models.default_model_id` (000022) widens: the trigger accepts an existing `models.id` **or** `<slug>/<model>` naming a
row of `endpoint_models` on a service endpoint. Agents' and pools' `default_model_id` gains a sibling
`default_route text` (FK by `(team_id, …)` is not possible across service rows, so a deferred constraint trigger checks it
is in the subject's effective routes at commit, `23514` `agents_default_route_allowed`); when `default_route` is set,
`default_model_id` holds the route's model name and the `models` FK is not applied (the FK moves to a check trigger,
CD-42).

### 7.4.2 Endpoints, models and prices

| Object | Definition |
|---|---|
| `model_endpoints` | `id text PRIMARY KEY CHECK (afs.ulid_ok(id,'mep'))`, `team_id text REFERENCES afs.teams (id) ON DELETE CASCADE` (NULL = service), `slug text NOT NULL CHECK (slug ~ '^[a-z][a-z0-9-]{1,30}$' AND slug <> 'bedrock')`, `display_name`, `description`, `owner` and `purpose` (both required when `team_id IS NOT NULL`, `23514`), `provider text NOT NULL` (FK to `inference_providers`, or `internal`; set from `afs.provider_for_host` for team endpoints by trigger), `protocols text[] NOT NULL` (non-empty subset of `openai_chat`, `openai_responses`, `openai_embeddings`), `location text NOT NULL CHECK (location IN ('external','corporate','in_namespace'))` (`in_namespace` only with `team_id`; `external` and `corporate` need `https://`, `23514`), `base_url text NOT NULL` (≤ 500), `ca_bundle text` (PEM, ≤ 16 KiB), `auth_kind text NOT NULL CHECK (auth_kind IN ('none','bearer','header','azure_federated','google_federated'))`, `auth_header text` (required for `header`), `metrics_port integer` (`in_namespace` only), `credential_mode text NOT NULL DEFAULT 'per_team' CHECK (… IN ('shared','per_team'))` (team endpoints: always `per_team`), `pricing_mode text NOT NULL CHECK (pricing_mode IN ('per_token','capacity','free'))`, `requires_terms boolean NOT NULL DEFAULT false`, `use_provider_cost boolean NOT NULL DEFAULT false`, `enabled boolean NOT NULL DEFAULT false`, `timeout_seconds integer NOT NULL DEFAULT 300 CHECK (5..3600)`, `max_body_mib integer NOT NULL DEFAULT 20 CHECK (1..100)`, `external_system_id text` (FK to `external_systems`), `builtin boolean NOT NULL DEFAULT false`; `UNIQUE (team_id, id)`; slug unique among service rows and unique per team **and** not equal to any service slug (trigger, `23505` `model_endpoints_slug_taken`). Creating or updating an endpoint whose `provider` is disabled → `23514` (`provider_disabled`) |
| Built-in rows | `openrouter`, `nous-portal`, `opencode` (service, off, `per_token`, `bearer`, `per_team`) seeded with no models; `azure-openai` and `vertex-ai` (off, `azure_federated` / `google_federated`). Their base URLs carry placeholders (`<resource>`, `<project>`, `<location>`) that a service admin must replace before `enabled = true` (`23514` `endpoint_base_url_placeholder`) |
| `endpoint_models` | `(endpoint_id, model_name)` PK, `team_id` (copied, for RLS on team endpoints), `max_output_tokens integer NOT NULL CHECK (1..1000000)`, `context_tokens integer`, `enabled boolean NOT NULL DEFAULT true`; `model_name` printable, ≤ 200, no `/` at the start. At most 500 per endpoint |
| `endpoint_model_prices` | `(endpoint_id, model_name, effective_from)` PK, `input_per_mtok_usd`, `output_per_mtok_usd`, `cached_input_per_mtok_usd numeric(14,6)` (≥ 0), `request_fee_usd numeric(14,8) NOT NULL DEFAULT 0`, `source text CHECK (source IN ('manual','price_list','transfer','provider'))`, `approved_by`; append-only (UPDATE and DELETE rejected by trigger, as `model_prices`) |
| `endpoint_price_proposals` | as `model_price_proposals` with `endpoint_id`, `model_name` and `team_id` (copied from the endpoint); `state` `pending`, `approved`, `rejected`, `superseded` (a newer proposal or an approved price replaced it; CD-62) |
| `endpoint_capacity_costs` | `(endpoint_id, team_id, effective_from)` PK, `monthly_usd` or `hourly_usd` (exactly one), `allocation text CHECK (allocation IN ('by_tokens','by_agent'))` |

### 7.4.3 Credentials, federation and statements

| Object | Definition |
|---|---|
| `endpoint_credentials` | `(endpoint_id, scope)` PK where `scope` is a team id or `_shared`; `team_id` (NULL for `_shared`), `secret_arn text NOT NULL` checked by `afs.secret_path(team, '_gateway', slug)` or `<prefix>/_service/gateway/<slug>` (`23514` `endpoint_credential_path`), `status text CHECK (status IN ('set','missing'))`, `rotated_at`. No value column (the existing guard test covers it) |
| `afs.secret_path` | Accepts the reserved scope `_gateway` beside `_shared` |
| `endpoint_federations` | `(endpoint_id, team_id)` PK, `kind text CHECK (kind IN ('azure','google'))`, Azure: `tenant_id`, `client_id` (UUID form); Google: `project_number` (digits), `pool_id`, `provider_id`, `project_id`, `location`; `status text CHECK (status IN ('pending','ready','failing'))`, `last_error text` (≤ 500), `checked_at`. Metadata only. Written by service admins (`afs_app`); `status`, `last_error`, `checked_at` also by `afs_gateway` (column grant) |
| `provider_statements` | `id` (`pst_`), `endpoint_id`, `period date` (first of month), `source text CHECK (source IN ('nous_statement','opencode_csv'))`, `rows jsonb NOT NULL` (array of `{teamId, model, amountUsd, tokens?}`, ≤ 10 000), `imported_by`, `imported_at`; `UNIQUE (endpoint_id, period, source)` |

### 7.4.4 Selections and agents

| Object | Definition |
|---|---|
| `team_model_endpoints` | `(team_id, endpoint_id)` PK, `selected_by text NOT NULL CHECK (selected_by IN ('team_admin','service_admin'))`, `created_at/by`. Insert of an endpoint with `requires_terms` or whose provider has `team_selection = 'service_admin'` without `afs.service_admin` → `42501`. Service endpoints only (team endpoints are always in their team's set) |
| `teams` | `may_add_model_endpoints boolean NOT NULL DEFAULT false` and `gateway_deployment text NOT NULL DEFAULT 'shared' CHECK (… IN ('shared','per_namespace'))`, both in `teams_guardrail_guard` (service admins only) |
| `agents`, `agent_pools` | `route_access text NOT NULL DEFAULT 'all' CHECK (… IN ('all','selected'))`, `default_route text` (§7.4.1) |
| `agent_model_endpoints`, `pool_model_endpoints` | `(team_id, agent_id|pool_id, endpoint_id)` PK, composite FK to the agent or pool `ON DELETE CASCADE`; the endpoint must be in the team's set at write time (`23514` `agent_routes_team`, for agents and pools); at most 50 rows per subject (`agent_model_endpoints_limit`, `pool_model_endpoints_limit`). Bedrock is never a row: it stays under `model_access` |
| `afs.effective_agent_routes` | View, `security_invoker`: `(team_id, subject_kind, subject_id, endpoint_id, slug, model_name, is_default)` for routes in (team's opted-in enabled service endpoints ∪ team endpoints that are enabled) ∩ subject, on enabled providers, for callable models (`per_token` needs a price in force) |
| `afs.route_admission(p_subject_kind, p_subject_id)` | `STABLE`, `SECURITY INVOKER`, returns `(endpoint_id, slug, model_name, reason)` for every route model reachable in principle for the subject's team; `reason` NULL or the first of `provider_disabled`, `route_not_enabled_for_service`, `route_not_enabled_for_team`, `route_not_enabled_for_agent`, `model_not_priced` (`model_not_on_route` is decided by the gateway for names absent from the result). Also `afs.provider_enabled(p_provider text) RETURNS boolean` for Bedrock paths |

### 7.4.5 Usage and cost

`usage_events` (partitioned) gains nullable `endpoint_id text`, `model_name text`, `usage_source text CHECK (… IN
('response','estimated','provider_cost'))`, `reasoning_tokens bigint`, `ttft_ms integer`, `upstream_ms integer`,
`gateway_ms integer`, `http_status smallint`; `model_id` becomes nullable with `CHECK ((model_id IS NULL) <>
(endpoint_id IS NULL) OR outcome <> 'ok')`. `cost_daily.source` accepts `route` and `route_capacity`. Columns are added on
the parent; no rewrite (metadata-only on PostgreSQL 17). Lock: `ACCESS EXCLUSIVE` on the parent briefly.

### 7.4.6 Grants, RLS and change feed

| Role | Grants |
|---|---|
| `afs_app` | `SELECT, INSERT, UPDATE, DELETE` on endpoint tables (RLS: team rows by `afs.caller_sees_team`; service rows readable by all callers, writable only with `afs.service_admin`); `SELECT, UPDATE (listed columns)` on `inference_providers`; `INSERT, SELECT` on `provider_statements`; `EXECUTE` on the functions |
| `afs_gateway` | `SELECT` on every 000023 table except `provider_statements`; `UPDATE (status, last_error, checked_at)` on `endpoint_federations`; `EXECUTE` on `afs.route_admission`, `afs.provider_enabled`; per-namespace gateways set `afs.team_ids` to their team |
| `afs_reconciler` | `SELECT` on every 000023 table; `UPDATE (status)` on `endpoint_credentials` |
| `afs_billing` | `SELECT` on endpoints, `endpoint_models`, prices, proposals, capacity costs, statements, federations; `INSERT` on `endpoint_price_proposals` and `UPDATE (state, note)` so billing can supersede its own proposals (approval stays with service admins) |
| `afs_readonly` | `SELECT` on every 000023 table |

Every team-owned new table (`model_endpoints` team rows, `endpoint_models`, `endpoint_credentials`,
`endpoint_federations`, `team_model_endpoints`, `agent_model_endpoints`, `pool_model_endpoints`,
`endpoint_capacity_costs`) enables RLS and gets rows in `seedOtherTeams`. Every new table notifies on change.

### 7.4.7 Error mapping (additions to §6)

| SQLSTATE and constraint | API |
|---|---|
| `23505` `model_endpoints_slug_taken` | `409 Conflict`, `details.reason = slug_taken` |
| `23514` `provider_disabled` | `400 ValidationError`, `provider_disabled` |
| `23514` `no_fallback_model` | `400 ValidationError`, `no_fallback_model` |
| `23514` `endpoint_credential_path`, `endpoint_base_url_placeholder`, `agent_routes_team`, `agents_default_route_allowed` | `400 ValidationError` with the constraint as reason |
| `42501` on selections of extra-terms or service-selected providers | `403 AccessDenied`, `needs_service_admin` |

### 7.4.8 Tests

TC-DB-01 to TC-DB-15 of the PRD; each constraint above has a rejected-case test; isolation and
`TestCrossTeamWritesChangeNothing` cover every team-owned table; up/down/up is clean.

## 7.5 Migration 000024: MCP servers, policy, ledger and federated identities (contract v1.6.0)

Source: [MCP gateway PRD](../../mcp-gateway-PRD.md) §7, §8, §11, §13.2 and Appendix C and E.2 (approved by J,
2026-11-25). Release `-db` 1.3.0 with `-restapi` 1.3.0; applies after 000023 (§7.4). All objects in schema `afs`; ids
are prefixed ULIDs (`mcp_`, `mpr_`, `mpol_`, `mcr_`, `mrv_`, `afi_`, `pfi_`, `mqc_`). Desired-state tables carry `version`,
`created_at/by`, `updated_at`, the touch and revision triggers and a notify trigger on `afs_desired_state` (payload
`<table>:<team_id>:<id>`, empty team for enterprise rows).

### 7.5.1 Catalog

| Object | Definition |
|---|---|
| `mcp_servers` | `id text PRIMARY KEY CHECK (afs.ulid_ok(id,'mcp'))`, `team_id text REFERENCES afs.teams (id) ON DELETE CASCADE` (NULL = enterprise), `slug text NOT NULL CHECK (slug ~ '^[a-z][a-z0-9-]{1,30}$' AND slug !~ '--' AND slug !~ '-$' AND slug <> 'afs')`, `display_name` (≤ 100), `owner`, `purpose` (≤ 1000), `doc_url`, `data_classification text NOT NULL CHECK (… IN ('public','internal','confidential','restricted'))`, `transport text NOT NULL CHECK (… IN ('streamable_http','hosted'))`, `location text NOT NULL CHECK (… IN ('external','corporate','in_namespace'))` (`hosted` ⇔ `in_namespace`; remote needs `url` with `https://`, `23514` `mcp_servers_url`), `url text` (≤ 500), `ca_bundle text` (PEM, ≤ 16 KiB), `auth_kind text NOT NULL CHECK (… IN ('none','static','oauth_client','workload_federation','oauth_user','aws_sigv4'))`, `auth_header text`, `credential_mode text NOT NULL DEFAULT 'per_team' CHECK (… IN ('shared','per_team'))`, `federation jsonb` (`{issuer, audience, subjectTemplate, tokenEndpoint, grant}`; required for `workload_federation`), `oauth jsonb` (`{authorizationServer, scopes[]}`; metadata only), `protocol_version text`, `review_status text NOT NULL DEFAULT 'draft' CHECK (… IN ('draft','pending_review','approved','rejected','suspended'))`, `published boolean NOT NULL DEFAULT false` (enterprise only; needs `approved`), `risk_tier text CHECK (… IN ('low','elevated','high'))`, `risk_reasons text[] NOT NULL DEFAULT '{}'`, `checks jsonb NOT NULL DEFAULT '[]'` (findings, never the offending text in full), `drift_policy text NOT NULL DEFAULT 'hold' CHECK (… IN ('hold','auto_approve_compatible'))`, `default_for_new_teams boolean NOT NULL DEFAULT false` (enterprise only), `allow_sampling boolean NOT NULL DEFAULT false`, `trust_annotations boolean NOT NULL DEFAULT false`, `args_hashing boolean NOT NULL DEFAULT false`, `limits jsonb NOT NULL DEFAULT '{}'`, `suspended_reason text`, `promoted_from text` (the team server id it was promoted from), `refresh_requested_at timestamptz` (set by `afs_app`, cleared by `afs_gateway`), `version`, `generation`; `UNIQUE (team_id, id)`. Slug unique among enterprise rows (partial unique index), unique per team, and a team slug never equals an enterprise slug nor the reverse (trigger, `23505` `mcp_servers_slug_taken`) |
| Review transitions | `BEFORE UPDATE` trigger allows `draft → pending_review`, `pending_review → approved \| rejected \| draft` (changes requested), `rejected → draft`, `approved → pending_review` (a change of `url`, `location`, `auth_kind` or hosted spec), any → `suspended` and `suspended →` the status before it (kept in `suspended_from`); else `23514` `mcp_review_transition`. `published = true` needs `approved` (`23514` `mcp_servers_publish`) |
| `mcp_hosted_specs` | `(server_id)` PK and FK `ON DELETE CASCADE`, `team_id` (copied), `image text NOT NULL CHECK (image ~ '^[^@]+@sha256:[0-9a-f]{64}$')` (`23514` `mcp_hosted_specs_image`), `args text[]`, `env_names text[]` (names only, `^[A-Z_][A-Z0-9_]{0,63}$`), `instance_mode text NOT NULL DEFAULT 'per_team' CHECK (… IN ('per_team','per_agent'))`, `egress_hosts text[] NOT NULL DEFAULT '{}'`, `resources jsonb`, `needs_aws boolean NOT NULL DEFAULT false`, `signature_verified_at timestamptz` |
| `mcp_primitives` | `id` (`mpr_`), `server_id` FK `ON DELETE CASCADE`, `team_id` (copied), `kind text NOT NULL CHECK (… IN ('tool','resource','resource_template','prompt'))`, `name text NOT NULL` (≤ 500), `title`, `summary` (≤ 200), `annotations jsonb NOT NULL DEFAULT '{}'`, `definition jsonb NOT NULL` (the approved definition, tool metadata only), `digest text NOT NULL CHECK (digest ~ '^sha256:[0-9a-f]{64}$')`, `approved_digest text` (same check), `pending_definition jsonb`, `status text NOT NULL CHECK (… IN ('approved','pending_review','blocked'))`, `decided_by`, `decided_at`, `first_seen`, `last_seen`, `removed_at`; `UNIQUE (server_id, kind, name)`. Transition guard: `pending_review → approved \| blocked`, `approved → pending_review` only with a changed `digest`, `blocked → approved` by review; else `23514` `mcp_primitive_transition`. At most 2,000 live primitives per server (`23514` `mcp_primitives_limit`) |

### 7.5.2 Opt-in, narrowing and policy

| Object | Definition |
|---|---|
| `teams` | `may_add_mcp_servers boolean NOT NULL DEFAULT false` and `mcp_placement text CHECK (… IN ('combined','separate'))` (NULL = service default), both in `teams_guardrail_guard` |
| `team_mcp_servers` | `(team_id, server_id)` PK, `enabled boolean NOT NULL`, `mode text NOT NULL DEFAULT 'full' CHECK (… IN ('full','read_only'))`, `enabled_by`, `enabled_at`, `version`. The server must be a published enterprise server or a server of the same team (trigger, `23514` `team_mcp_servers_scope`); `enabled = true` needs `teams.gateway_deployment = 'per_namespace'` (`23514` `team_gateway_required`, CD-44) |
| `agents`, `agent_pools` | `mcp_access text NOT NULL DEFAULT 'all' CHECK (… IN ('all','selected'))`, `mcp_mode text CHECK (… IN ('search','full'))` (NULL = `mcp.default_agent_mode`) |
| `agent_mcp_servers`, `pool_mcp_servers` | `(team_id, agent_id\|pool_id, server_id)` PK, composite FK to the agent or pool `ON DELETE CASCADE`; the server must be enabled for the team at write time (`23514` `agent_mcp_servers_team`) |
| `mcp_policies` | `id` (`mpol_`), `level text NOT NULL CHECK (… IN ('service','team','agent','pool'))`, `team_id`, `agent_id`, `pool_id`, `server_id` FK, `name text` or `class text CHECK (… IN ('read_only','destructive','open_world'))` (exactly one), `effect text NOT NULL CHECK (… IN ('allow','block'))`, `rate_limit_per_minute integer CHECK (> 0)`; CHECK that level and scope columns agree (`service`: no team; `team`: team only; `agent`/`pool`: team and subject); composite FKs `(team_id, agent_id)` and `(team_id, pool_id)`. At most 500 rules per server per scope |
| `afs.mcp_admission(p_subject_kind text, p_subject_id text)` | `STABLE`, `SECURITY INVOKER`; returns `(server_id, slug, server_kind, mode, primitive_id, kind, name, digest, allowed, level, reason, rate_limit_per_minute)` for every primitive of every server the subject's team could reach; `reason` NULL or the first of the gateway contract §13.4 list. Read-only mode, trusted annotation classes and a block at any level winning are applied here, so the gateway and the API share one decision |
| `afs.effective_agent_mcp` | View, `security_invoker`: the allowed rows of `afs.mcp_admission` for every agent and pool, for `GetEffectiveAgentMcp` and the reconciler's `/etc/afs/mcp.json` |
| `afs.create_team` (and `afs.instantiate_work_order_team`) | Switch on every published enterprise server with `default_for_new_teams` for a new team (mode `full`), writing `team_mcp_server.enabled` outbox rows; skipped while the new team's gateway is `shared` |

### 7.5.3 Credentials, reviews, captures and federated identities

| Object | Definition |
|---|---|
| `mcp_credentials` | `id` (`mcr_`), `server_id` FK, `scope text NOT NULL` (team id or `_shared`), `team_id` (NULL for `_shared`), `kind text NOT NULL CHECK (… IN ('static','oauth_client','oauth_user'))`, `secret_arn text NOT NULL` checked by `afs.secret_path(team, '_gateway', 'mcp/' || slug)` or `<prefix>/_service/gateway/mcp/<slug>` (`23514` `mcp_credential_path`), `subject text` (connected account display name), `scopes text[]`, `expires_at`, `status text NOT NULL CHECK (… IN ('set','missing','expired'))`, `rotated_at`; `UNIQUE (server_id, scope)`. No value column. `oauth_user` rows must name a `subject` (`23514` `service_account_required` is decided by the API; the column records who) |
| `afs.secret_path` | Accepts `_gateway` with the sub-path `mcp/<slug>` |
| `mcp_oauth_states` | `state_hash text PRIMARY KEY` (sha256 of the state), `team_id`, `server_id`, `created_by`, `code_verifier_arn` (ARN only), `expires_at` (≤ 10 minutes), `used_at`. Single use (`UPDATE … SET used_at` only when NULL). Deny-all RLS for `afs_app` except through `afs.claim_mcp_oauth_state(p_state_hash)` (`SECURITY DEFINER`) |
| `mcp_reviews` | `id` (`mrv_`), `server_id`, `team_id`, `primitive_id` (NULL for a server review), `at`, `checks jsonb`, `risk_tier`, `approver text CHECK (… IN ('team_admin','security'))`, `decision text CHECK (… IN ('approved','rejected','changes_requested','blocked','auto_approved'))`, `note` (≤ 2000, required for every decision but `auto_approved`), `decided_by`. Append-only by trigger |
| `mcp_federation_states` | `(server_id, team_id)` PK, `status text NOT NULL DEFAULT 'pending' CHECK (… IN ('pending','ready','failing'))`, `last_error text` (≤ 500), `checked_at`, `test_requested_at`. `afs_app` writes `test_requested_at`; `afs_gateway` writes the rest (column grants) |
| `mcp_query_captures` | `id` (`mqc_`), `started_by`, `reason`, `started_at`, `until` (≤ `mcp.query_capture_max_days`), `stopped_at`, `stopped_by`. At most one open row (partial unique index, `23505` `capture_active`) |
| `agent_federated_identities`, `pool_federated_identities` | `(team_id, agent_id\|pool_id, name)` PK, `id` (`afi_` / `pfi_`), `name text CHECK (name ~ '^[a-z][a-z0-9-]{0,30}$')`, `audience text NOT NULL` (≤ 300; not `sts.amazonaws.com` and not `afs-gateway`, `23514` `audience_reserved`), `file_path text NOT NULL` (default `/var/run/secrets/afs/federation/<name>/token`, must start with `/var/run/secrets/afs/federation/`), `env_var text NOT NULL` (default `AFS_FEDERATED_TOKEN_FILE_<NAME>`, `^[A-Z_][A-Z0-9_]{0,63}$`), `expiration_seconds integer NOT NULL DEFAULT 3600 CHECK (600..86400)`, `created_at/by`, `version`; composite FK to the agent or pool `ON DELETE CASCADE`; at most 10 per subject (`23514` `federated_identity_limit`). The audience must match `federation.allowed_audiences` (trigger, `23514` `audience_not_allowed`) |
| `external_systems` | `category` accepts `mcp`; `afs.mcp_governed_host(p_host)` returns the MCP server id that covers a host, and a grant of an `mcp` system whose host is covered is refused (`23514` `governed_by_mcp_server`) |

### 7.5.4 Ledger and rollups

| Object | Definition |
|---|---|
| `mcp_events` | Partitioned by `RANGE (at)`, one partition per day created ahead by `afs.ensure_mcp_event_partitions(days)`; `id bigint` (identity), `at timestamptz NOT NULL`, `request_id text NOT NULL`, `team_id text NOT NULL`, `agent_id`, `pool_id`, `worker_pod`, `server_id`, `server_kind text CHECK (… IN ('enterprise','team','afs'))`, `method text NOT NULL` (≤ 64), `name text` (≤ 500; normalised resource URI or template), `primitive_id`, `digest`, `outcome text NOT NULL CHECK (… IN ('ok','tool_error','protocol_error','refused','upstream_unavailable','timeout','cancelled'))`, `reason text`, `jsonrpc_code integer`, `http_status smallint`, `gateway_ms integer`, `upstream_ms integer`, `request_bytes integer`, `response_bytes integer`, `auth_kind`, `protocol_downstream`, `protocol_upstream`, `args_sha256 text CHECK (~ '^[0-9a-f]{64}$')`, `search_results text[]` (qualified names, `afs_search` only), `search_hit boolean`, `query_text text` (only while a capture row is open; trigger nulls it otherwise, CD-50), `capture_id`. Append-only (UPDATE, DELETE and TRUNCATE rejected by trigger, as `audit_log`); retention drops whole partitions older than `mcp.events_retention_months` (`afs.drop_old_mcp_event_partitions()`) |
| `mcp_usage_daily` | `(day, team_id, agent_or_pool, server_id, method, name, outcome)` PK, `calls bigint`, `errors bigint`, `p50_ms`, `p95_ms`, `bytes_in`, `bytes_out`; written by `afs.rollup_mcp_usage(p_day date)` (idempotent: replaces the day) |

### 7.5.5 Grants, RLS and change feed

| Role | Grants |
|---|---|
| `afs_app` | `SELECT, INSERT, UPDATE, DELETE` on the catalog, opt-in, selection, policy, credential, federated identity and capture tables (RLS: team rows by `afs.caller_sees_team`; enterprise rows readable by all callers, writable only with `afs.service_admin`; security operators reach every row through `afs.service_admin`-free read paths of `SECURITY DEFINER` functions `afs.mcp_review_queue()` and `afs.mcp_events_for_review(…)`); `INSERT, SELECT` on `mcp_reviews`; `SELECT` on `mcp_events` and `mcp_usage_daily`; `EXECUTE` on the functions |
| `afs_gateway` | `SELECT` on every 000024 table except `mcp_oauth_states` and `mcp_query_captures` (it reads the open capture through `afs.mcp_capture_open()`); `INSERT` on `mcp_events` for its team only (`afs.team_ids`, RLS `WITH CHECK`); `INSERT, UPDATE (digest, pending_definition, status, last_seen, removed_at, title, summary, annotations)` on `mcp_primitives` (a gateway can hold a change, never approve one: a trigger refuses `status = 'approved'` from `afs_gateway` unless `drift_policy = 'auto_approve_compatible'` and the row is marked compatible); `UPDATE (status, expires_at)` on `mcp_credentials`; `UPDATE (status, last_error, checked_at)` on `mcp_federation_states`; `UPDATE (refresh_requested_at, protocol_version)` on `mcp_servers`; `EXECUTE` on `afs.mcp_admission` |
| `afs_reconciler` | `SELECT` on every 000024 table; `UPDATE (signature_verified_at)` on `mcp_hosted_specs`; `UPDATE (stopped_at, stopped_by)` on `mcp_query_captures`; `EXECUTE` on the partition and rollup functions |
| `afs_billing` | `SELECT` on `mcp_usage_daily` |
| `afs_readonly` | `SELECT` on every 000024 table except `mcp_oauth_states` |

Every team-owned new table (`mcp_servers` team rows, `mcp_hosted_specs`, `mcp_primitives`, `team_mcp_servers`,
`agent_mcp_servers`, `pool_mcp_servers`, `mcp_policies` team, agent and pool rows, `mcp_credentials`, `mcp_reviews`,
`mcp_oauth_states`, `mcp_federation_states`, `agent_federated_identities`, `pool_federated_identities`, `mcp_events`, `mcp_usage_daily`) enables
RLS and gets rows in `seedOtherTeams`. The catalog, opt-in, selection, policy, primitive and credential tables notify
on change.

### 7.5.6 Error mapping (additions to §6)

| SQLSTATE and constraint | API |
|---|---|
| `23505` `mcp_servers_slug_taken` | `409 Conflict`, `details.reason = slug_taken` |
| `23505` `capture_active` | `409 Conflict`, `capture_active` |
| `23514` `team_gateway_required` | `409 Conflict`, `team_gateway_required` |
| `23514` `mcp_review_transition`, `mcp_primitive_transition` | `409 Conflict`, `invalid_review_transition` |
| `23514` `mcp_servers_publish` | `409 Conflict`, `server_not_approved` |
| `23514` `team_mcp_servers_scope` | `409 Conflict`, `server_not_published` |
| `23514` `federated_identity_limit` | `409 Conflict`, `federated_identity_limit` |
| `23514` `governed_by_mcp_server` | `409 Conflict`, `governed_by_mcp_server` |
| `23514` `audience_reserved`, `audience_not_allowed`, `mcp_credential_path`, `mcp_servers_url`, `mcp_hosted_specs_image`, `agent_mcp_servers_team`, `mcp_primitives_limit` | `400 ValidationError` with the constraint as reason (`mcp_hosted_specs_image` → `image_not_pinned`, `agent_mcp_servers_team` → `mcp_server_not_enabled_for_team`) |

### 7.5.7 Tests

`TestMcpServers/*`, `TestMcpPrimitives/*`, `TestMcpAdmission/*`, `TestMcpCredentials/*`, `TestMcpEvents/*` and
`TestFederatedIdentities/*` (PRD Appendix E.2 and TC-47 to TC-62); each constraint above has a rejected-case test;
isolation and `TestCrossTeamWritesChangeNothing` cover every team-owned table; up/down/up is clean.

| # | Decision |
|---|---|
| CD-50 | `query_text` can only be written while a capture window is open: a trigger on `mcp_events` sets it to NULL when `afs.mcp_capture_open()` is false, so a gateway bug cannot store query text outside the audited window |
| CD-51 | The policy decision lives in `afs.mcp_admission`, not in the gateway alone, so the API's effective view (`GetEffectiveAgentMcp`), the reconciler's `/etc/afs/mcp.json` and the gateway's admission can never disagree. The gateway's pure policy package re-implements the same rules for its cache and is tested against the function |
| CD-52 | The gateway may write held definitions and digests but never approve, except auto-approval under `auto_approve_compatible`, so the review boundary is enforced by the database as well as by the API |

## 8. Change process

1. Schema change: a `-db` PR with the migration, integration tests (rejected case for every new
   constraint; RLS isolation for every new team table), `docs/data-model.md`, and this contract when §2
   to §6 change. Tag a release after merge.
2. `-restapi` adopts the tag in its own PR (`go get …@vX.Y.Z`), with repository tests against the new
   schema.
3. A breaking change follows expand and contract across two `-db` releases.

## 9. Change log

- **v1.6.0 (2026-11-25), governed MCP servers ([PRD](../../mcp-gateway-PRD.md), approved by J):** migration 000024
  (§7.5): `mcp_servers` with review transitions and the enterprise and team slug rule, hosted specs pinned by digest,
  `mcp_primitives` with pinning and a transition guard, team switches gated on a per-namespace gateway, agent and pool
  selections and modes, `mcp_policies` at four levels, `afs.mcp_admission` and `afs.effective_agent_mcp`,
  default-for-new-teams in `create_team`, `mcp_credentials` at `_gateway/mcp` paths, OAuth states, federation states,
  reviews, query captures, agent and pool federated identities, the partitioned append-only `mcp_events` ledger and
  `mcp_usage_daily`, `teams.may_add_mcp_servers` and `mcp_placement`, the `mcp` external system category; CD-50 to
  CD-52. Minor (1.3.0).

- **v1.5.0 amendment (2026-11-25), build of `-db` 000023 (PR #23, release 1.2.0):** records where the build read §7.4
  (the `-db` spec's implementation notes list all of them); additive. Proposal state `superseded` and the
  `afs_billing` grants (§7.4.2, §7.4.6); the 50-route limit per agent or pool (§7.4.4). Decisions CD-61 to CD-66.

| # | Decision |
|---|---|
| CD-61 | `model_endpoints.provider` is set by trigger from the base URL host (`afs.provider_for_host`) for every endpoint, team or service; a claimed provider is overwritten. A corporate host that matches a listed provider gets that provider and its switch; only unlisted corporate hosts and in-namespace Services are `internal`. A service admin may name a provider only for an external host that matches none. In-namespace hosts are a bare Service name or `<svc>.<team namespace>[.svc[.cluster.local]]`, and only they may use `http` |
| CD-62 | Proposals and prices carry `team_id` (copied from the endpoint) so RLS and composite keys cover them. Prices are written by service admins only, also for team endpoints. `cached_input_per_mtok_usd` NULL bills cached input at the input price |
| CD-63 | `provider_disabled` applies to an insert, to an update that leaves or turns an endpoint on, and to a provider change; an endpoint of a disabled provider may be edited while it stays off. While Bedrock is off, the fallback route's provider cannot be turned off and the service default must stay a valid fallback (`no_fallback_model`). The Bedrock switch also gates `effective_agent_models` and `model_admission` (`provider_disabled` first) |
| CD-64 | New teams are selected for the service default route (`teams_default_route_select`, `selected_by service_admin`), so "every live team has selected it" keeps holding while Bedrock is off. A service-admin selection is removed by service admins only. Disabled route models are absent from `route_admission`; a team endpoint that is off reports `route_not_enabled_for_team` |
| CD-65 | Status columns written by runners (`endpoint_credentials.status`, `endpoint_federations.status, last_error, checked_at`) do not bump `version`, so client ETags survive; revision and change-feed triggers still fire. No credential row for `none` or federated endpoints (`endpoint_credentials_auth_kind`). `provider_statements` are readable by service admins only through `afs_app`; the gateway cannot read them |
| CD-66 | `afs-migrate down 1` refuses (`55000`) while an agent or pool has `default_route` set. `cost_daily.model_id` holds `<route>/<model>` for route rows (the route alone for capacity rows); `models.default_model_id` widens to 240 characters. Change-feed ids are `id`, else `endpoint_id`, else the provider (`inference_providers::bedrock`) |

- **v1.5.0 (2026-11-25), team model gateway ([PRD](../../model-endpoint-gateway-PRD.md), approved by J):** migration 000023
  (§7.4): `inference_providers` with the Bedrock-off guard, model endpoints, route models, prices and proposals,
  credentials at `_gateway` paths, federation metadata, provider statements, team selections, agent and pool routes,
  `teams.may_add_model_endpoints` and `gateway_deployment`, `afs.route_admission`, `afs.effective_agent_routes`,
  `afs.provider_enabled`, `afs.provider_for_host`, usage row columns. Minor (1.2.0).

| # | Decision |
|---|---|
| CD-42 | A default model may be a route model: `default_route` plus `default_model_id` holding the route's model name. The FK of `default_model_id` to `models` becomes a check trigger that applies only when `default_route` is NULL |
| CD-43 | Built-in service endpoints ship off with placeholder base URLs that must be replaced before they can be switched on |

- **v1.4.0 (2026-11-23), team orchestration agent and model access ([PRD](../../team-orchestration-agent-PRD.md), approved by J):** migration 000022 (§7.3): role `collaboration` renamed `orchestration` with `agents_team_orchestration_uq`; `teams.orchestration_required` and its deferred check; reserved name `orchestrator`; delete guard; `team_collaboration.tool`, `web_ui_exposure`, `web_api_exposure` and `teams.max_collaboration_exposure`, kept in step with the 1.0.1 booleans; exposure check trigger; capabilities `orchestration`, `tool:paperclip`, `tool:buzz`; `orchestration.*` and `models.*` settings; `afs.orchestration_routes()`, `afs.orchestration_settings()`, `exposure` in `record_collab_access` and `collaboration_access`; `afs.create_orchestration_agent`; work order teams get an orchestration agent; Buzz reserved secret names; model access columns and tables (`teams.model_access`, `agents`/`agent_pools.model_access` and `default_model_id`, `agent_models`, `pool_models`, `team_inference_profiles`), view `afs.effective_agent_models` and `afs.model_admission`. Minor (1.1.0); removals in 2.0.0.

Contract decisions recorded with v1.4.0 (the PRD is silent on these; the API contract continues the numbering at CD-26):

| # | Decision |
|---|---|
| CD-13 | `team_models` stays the team's *selection* and is read only in `selected` mode. Inference profiles move to the reconciler-owned `team_inference_profiles` (one row per callable model, 7-day `retiring` grace), because a team in `all` mode has no `team_models` rows to hold an ARN. `team_models.inference_profile_arn` is kept in step until 2.0.0 for 1.0.1 readers |
| CD-14 | The composite FKs from `agents` and `agent_pools` to `team_models` are dropped and replaced by write-time checks (service and team allow the model; the default is in the stored selection), deferred to commit. A price is not required at write time; the gateway refuses an unpriced model with `model_not_priced` and the reconciler sets `ModelUnavailable` |
| CD-15 | The exposure check runs only for a surface whose level is new or changed, and for both surfaces when the tool changes. A stored level above a lowered limit is never re-checked, so lowering a limit cannot block an unrelated update (ORC-14 "keeps the choice") |
| CD-16 | Booleans and levels: on insert the levels win; on update a changed level wins, else a changed boolean maps `false` → `off` and `true` → the team's limit (or `off` when the tool lacks the surface or the limit is `off`). The same pattern keeps `may_expose_collaboration` and `max_collaboration_exposure` in step |
| CD-17 | `orchestration.tools` entries carry the tool's fixed capability profile (`webUi`, `webApi`, `registration`, `inNamespacePort`) and an `imageRepository`. The orchestration agent's image is `imageRepository@<template current digest>`, so `CreateTeam` needs no image from the caller. This replaces DB-D18 for orchestration agents. A tool whose `templateId` or `imageRepository` is unset cannot create an agent (`orchestration_runtime_unset`) |
| CD-18 | "Upgrade" for the `models.service_access` seed means `afs.models` has at least one row when 000022 runs. `models.default_model_id` is seeded `null`, because 1.0.1 has no service default model |
| CD-19 | The name `orchestrator` is reserved on insert only (names are immutable). A 1.0.1 worker or pool already named `orchestrator` keeps it; the backfill then names that team's agent `team-orchestrator` |
| CD-20 | `collaboration_access.surface` keeps the 1.0.1 value `rest_api` for the Web API; the new functions say `web_api` and `record_collab_access` accepts both |
| CD-21 | `afs.create_orchestration_agent` writes the agent, its `team_collaboration` row and model rows, the audit record and the `agent.created` and `orchestration.created` outbox rows, and sets `orchestration_required`, so `CreateTeam`, the backfill and work order teams share one code path. It needs a service admin session |
| CD-22 | Backfill statements in 000022 run with the touch, revision and notify triggers of the table disabled, so `version` and ETags do not change and no revision is recorded for a mechanical rename; reconcilers resync at start-up |
| CD-23 | A *Change tool* snapshot is an `agent_volume_snapshots` row with reason `pre_tool_change`, the old `tool` and `retain_until = now() + 90 days`, inserted by `afs-api` in the `ChangeCollaborationTool` transaction |
| CD-24 | The capability value `paperclip` written by a 1.0.1 client is rewritten to `orchestration` + `tool:paperclip` by trigger until 2.0.0 |
| CD-25 | `collab.base_domain` and `collab.public_endpoints` become read-only aliases: the new keys write them; a direct write is refused (`setting_renamed`). The other five `collab.*` keys stay as they are |

- **v1.3.2 (2026-11-22), build of the Paperclip collaboration change:** migration 000021 (`collab_routes()` returns `provider_client_id` and `provider_cli_client_id`), §7.2.10 records facts about 000020 (change feed payload, revision key, deny-all edge session policies, `PUBLIC` execute revoked on partition helpers, team group bindings carry no provider), and §7.2.9 states that a swarm collaboration agent takes the first pool's model and image (DB-D18).
