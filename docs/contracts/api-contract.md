# API contract: `-restapi` ↔ `-cli`, `@afs/sdk` and the console

| | |
|---|---|
| **Status** | Contract v1, draft for implementation (2026-11-21) |
| **Provider** | [enterprise-agent-factory-service-restapi](https://github.com/stainedhead/enterprise-agent-factory-service-restapi) (`afs-api`) |
| **Consumers** | [-cli](https://github.com/stainedhead/enterprise-agent-factory-service-cli) (`afs`), [-website](https://github.com/stainedhead/enterprise-agent-factory-service-website) (`@afs/sdk`, console) |
| **Machine-readable form** | `-restapi/api/openapi.yaml` (OpenAPI 3.1). Built from this document; once an operation is in the YAML, the YAML wins and this document is updated to match in the same PR |
| **Requirements** | [Root PRD](../../enterprise-agent-factory-service-initial-PRD.md) §6; [solution design](../solution-design.md) §5, §10 |

This contract fixes everything a client may rely on: conventions, authentication, the permission
catalog, every operation (with its permission, CLI command, SDK method and console screen), resource
shapes, errors and events. A client never decides access; it reads `GET /v1/me` only to shape the UX.

## 1. Conventions

| Topic | Rule |
|---|---|
| Base | `https://<host>/v1`, JSON (`application/json; charset=utf-8`), UTF-8, camelCase fields |
| Ids | Server-generated prefixed ULIDs: `team_`, `agt_`, `pool_`, `stg_`, `sec_`, `rb_`, `key_`, `usr_`, `idp_`, `ext_`, `arl_`, `prl_`, `aid_`, `ncv_`, `acv_`, `pcv_`, `bud_`, `mpp_`, `vsnap_`, `wo_`, `swt_`, `exp_`, `rsc_`, `log_`, `nch_`, `egr_`, `xso_`, the same prefixes as the database contract. Clients treat them as opaque strings |
| Names | Team `slug`, agent `name`, secret `name`: `^[a-z][a-z0-9-]{1,38}[a-z0-9]$`, immutable after create |
| Timestamps | RFC 3339 UTC with `Z` (`2026-11-21T18:00:00Z`) |
| Money | Decimal string with up to 6 fraction digits, USD only (`"1234.50"`). Never a JSON number |
| Pagination | `?maxResults=1..100` (default 50) and `?nextToken=…` → `{"items": [...], "nextToken": "…"}`. `nextToken` absent on the last page. Tokens are opaque and expire after 24 h |
| Filtering | Query parameters named after fields (`?state=active&kind=ephemeral`). Unknown parameters → `ValidationError` |
| Concurrency | Every mutable resource has `version` (integer) and is returned with `ETag: "<version>"`. `PATCH`, `PUT` and `DELETE` on an existing resource require `If-Match`; a mismatch → `412 PreconditionFailed` |
| Idempotency | `POST` that creates (and `POST …:verb` actions) accepts `Idempotency-Key` (1–255 chars). Keys are scoped to the calling principal and kept for service setting `api.idempotency_key_ttl_seconds` (default 3600, so 1 hour). A repeat with the same key and the same operation and body returns the stored status and body with header `Idempotent-Replayed: true`; the same key with a different body or operation → `409 Conflict` (`details.reason = idempotency_mismatch`); a repeat while the first is still running → `409 Conflict` (`details.reason = idempotency_in_progress`, `Retry-After: 1`). Error responses of 5xx are not stored, so a retry runs again |
| Actions | Non-CRUD verbs are `POST …/{id}:verb` (`:suspend`, `:restart`, `:approve`) |
| Async | Mutations return the stored desired state at once with `status.phase` `Pending`. Clients poll `GET …` (or `…/status`) until `Ready`, `Degraded` or `Failed`. `status.observedGeneration` equals `generation` when applied |
| Request id | Every response has `X-Request-Id`; a client may send its own (≤ 64 chars). It appears in errors and audit |
| Versioning | Additive changes (new optional field, new operation, new enum value documented as open) are minor. Removing or renaming a field, changing a type or making a field required is a new major path (`/v2`). Clients ignore unknown fields |
| Rate limits | 429 `Throttled` with `Retry-After` seconds. Default 20 req/s per principal, burst 40 |
| CSV | Report and list endpoints marked *CSV* also answer `Accept: text/csv` |

### 1.1 Status object

Every desired-state resource carries:

```json
"status": {
  "phase": "Pending | Reconciling | Ready | Degraded | Failed | Deleting",
  "observedGeneration": 7,
  "conditions": [{"type": "NamespaceReady", "status": "True|False|Unknown", "reason": "…", "message": "…", "lastTransitionTime": "…"}],
  "updatedAt": "…"
}
```

## 2. Authentication

| Client | Flow | Credential sent |
|---|---|---|
| Console | OIDC authorization code + PKCE against the team's or the default provider (`GET /v1/identity-providers`) | `Authorization: Bearer <IdP access token>` |
| CLI | OIDC device authorization grant (`afs sso login`) | Same; cached under `~/.afs/sso/cache` (0600) |
| Pipelines | Team API key (`afsk_…`), created once and shown once | `Authorization: Bearer afsk_…` |
| Security tooling | Service-level API key with the `security_operator` role (created by service admins) | `Authorization: Bearer afsk_…` |

The API validates IdP tokens against the provider's JWKS (any enabled service-level provider). The
groups claim (`groupsClaim` of the provider) maps to group role bindings. For a team-scoped request, a
group binding counts only when the token's issuer is the team's provider (or the default provider when
the team has none). Team API keys carry one team and one role (`team_admin` or `team_viewer`). Service-level API keys
carry no team and only the `security_operator` role. Security operators (people bound to the role, or
those keys) can use only the work order operations and `GetMe`; `afs-api` sets `afs.security_operator`
for them so the database lets them read and write work orders across teams.

`401 Unauthenticated` for a missing, expired or unknown credential; `403 AccessDenied` for a valid
caller without the permission.

## 3. Permission catalog

The catalog is implemented once, in `-restapi/internal/authz`. `-website/apps/console/src/domain/permission.ts`
mirrors it for UX. A change here is a change in both, in the same cycle.

| Permission | Viewer | Team-admin | Service admin | Notes |
|---|:-:|:-:|:-:|---|
| `teams:read` | ✓ | ✓ | ✓ | A team role sees only its bound teams |
| `teams:write` | | ✓ | ✓ | Display name, description, owner, sign-in provider |
| `teams:suspend` | | ✓ | ✓ | Suspend and resume |
| `teams:create`, `teams:delete` | | | ✓ | |
| `teams:set-guardrails` | | | ✓ | Ceiling, quotas, isolation tier, models, `mayManageAwsAccounts`, `mayAddExternalSystems` |
| `teams:set-aws-accounts` | | ✓ when `mayManageAwsAccounts` | ✓ | Checked by the API and again by the database |
| `members:read` / `members:write` | ✓ / | ✓ / ✓ | ✓ / ✓ | Team-admins cannot grant `service_admin` |
| `api-keys:read` / `api-keys:write` | ✓ / | ✓ / ✓ | ✓ / ✓ | |
| `agents:read` / `agents:write` | ✓ / | ✓ / ✓ | ✓ / ✓ | Write covers pause, resume, restart, snapshot |
| `secrets:read-metadata` / `secrets:write` | ✓ / | ✓ / ✓ | ✓ / ✓ | No permission reads a value |
| `config:read` / `config:write` | ✓ / | ✓ / ✓ | ✓ / ✓ | Namespace and agent configuration values |
| `identities:read` / `identities:write` | ✓ / | ✓ / ✓ | ✓ / ✓ | Agent IAM identity, role links, external identities |
| `external-systems:read` / `external-systems:write` | ✓ / | ✓ / ✓ | ✓ / ✓ | Team and agent switches; declare when `mayAddExternalSystems` |
| `budgets:read` / `budgets:write` | ✓ / | ✓ / ✓ | ✓ / ✓ | Amount ≤ ceiling |
| `usage:read` | ✓ | ✓ | ✓ | Usage, costs, reconciliation |
| `reports:read`, `reports:schedule` | ✓ | ✓ | ✓ | Own teams and their agents |
| `tags:read` / `tags:write` | ✓ / | ✓ / ✓ | ✓ / ✓ | Team tags and required values |
| `logs:read` / `logs:write` | ✓ / | ✓ / ✓ | ✓ / ✓ | |
| `notifications:read` / `notifications:write` | ✓ / | ✓ / ✓ | ✓ / ✓ | |
| `audit:read`, `revisions:read` | ✓ | ✓ | ✓ | Own teams |
| `revisions:restore` | | ✓ | ✓ | |
| `models:read` | ✓ | ✓ | ✓ | Enabled models |
| `admin:settings`, `admin:models`, `admin:pricing`, `admin:identity-providers`, `admin:service-tags`, `admin:external-systems`, `admin:storage-classes`, `admin:accounts`, `admin:reports`, `admin:audit`, `admin:export` | | | ✓ | Service level |
| `pools:read` / `pools:write` | ✓ / | ✓ / ✓ | ✓ / ✓ | Stages, pools, handoffs, pool secrets, config, external systems and role links; ephemeral teams only. Write covers scale, pause, resume |
| `teams:get-kubeconfig` | ✓ when `viewerKubectl` | ✓ when `viewerKubectl` | ✓ | Read-only kubeconfig for the namespace (ACC-5). Service admins turn it on with `teams:set-guardrails` |
| `work-orders:read` | ✓ assigned or own repos | ✓ assigned or own repos | ✓ | Security operators: all work orders |
| `work-orders:write` | | | ✓ | Security operators: create, update, cancel. A remediation team's agents and pools report repository progress with `work-orders:report` |
| `work-orders:report` | | ✓ on the assigned team | ✓ | Update the status and PR of the assigned work order's repositories |
| `admin:swarm-templates`, `admin:cost-tag-status` | | | ✓ | Service level |

**Security operator** (service-level role, D18): `work-orders:read` and `work-orders:write` on every
work order, and nothing else. It cannot be granted by team-admins and never appears in a team binding.

Service admins hold every permission on every team. `GET /v1/me` returns, per bound team, the
effective permission list; for service admins it returns `"serviceAdmin": true` and the full list;
for security operators `"securityOperator": true` with `work-orders:read` and `work-orders:write`.

## 4. Operations

Columns: **Op** = OpenAPI `operationId`; **Perm** = permission (team-scoped unless marked *svc*);
**CLI** = `afs <service> <operation>`; **SDK** = `@afs/sdk` method; **Screen** = console screen in the
root PRD §5.3. Every mutation writes the row, an audit record and an outbox event in one transaction.
P = priority from the root PRD.

### 4.1 Caller and sign-in

| Op | Method and path | Perm | CLI | SDK | Screen | P |
|---|---|---|---|---|---|---|
| `GetMe` | `GET /v1/me` | any signed-in | `sso get-caller-identity` | `me.get()` | header, all | P0 |
| `ListSignInProviders` | `GET /v1/identity-providers` | none (public) | `sso list-providers` | `auth.listProviders()` | sign-in | P0 |

### 4.2 Teams

| Op | Method and path | Perm | CLI | SDK | Screen | P |
|---|---|---|---|---|---|---|
| `ListTeams` | `GET /v1/teams` | `teams:read` | `teams list-teams` | `teams.list()` | S2, team switcher | P0 |
| `CreateTeam` | `POST /v1/teams` | `teams:create` *svc* | `teams create-team` | `teams.create()` | S3, P2 | P0 |
| `GetTeam` | `GET /v1/teams/{teamId}` | `teams:read` | `teams describe-team` | `teams.get()` | T1, V1 | P0 |
| `UpdateTeam` | `PATCH /v1/teams/{teamId}` | `teams:write`; guardrail fields `teams:set-guardrails`; `allowedAwsAccounts` `teams:set-aws-accounts` | `teams update-team` | `teams.update()` | T1, S6 | P0 |
| `DeleteTeam` | `DELETE /v1/teams/{teamId}` | `teams:delete` *svc* | `teams delete-team` | `teams.delete()` | S2 | P0 |
| `SuspendTeam` / `ResumeTeam` | `POST /v1/teams/{teamId}:suspend` / `:resume` | `teams:suspend` | `teams suspend-team` / `resume-team` | `teams.suspend()` / `resume()` | S2, T1 | P0 |
| `GetTeamStatus` | `GET /v1/teams/{teamId}/status` | `teams:read` | `teams get-team-status` | `teams.getStatus()` | T1 | P0 |
| `ListTeamModels` / `PutTeamModels` | `GET`/`PUT /v1/teams/{teamId}/models` | `teams:read` / `teams:set-guardrails` | `teams list-team-models` / `put-team-models` | `teams.models.list()` / `put()` | S3, T1 | P0 |
| `GetTeamTags` | `GET /v1/teams/{teamId}/tags` | `tags:read` | `teams get-team-tags` | `teams.tags.get()` | T13 | P1 |
| `PutTeamTags` | `PUT /v1/teams/{teamId}/tags` | `tags:write` | `teams put-team-tags` | `teams.tags.put()` | T13, S3 | P1 |
| `ListAllowedAccounts` | `GET /v1/teams/{teamId}/allowed-accounts` | `identities:read` | `teams list-allowed-accounts` | `teams.allowedAccounts.list()` | S6, T8 | P1 |
| `GetTeamKubeconfig` | `GET /v1/teams/{teamId}/kubeconfig` (YAML, `exec` credential plugin, no token in the file) | `teams:get-kubeconfig` | `teams get-kubeconfig` | `teams.getKubeconfig()` | T1, V1 | P2 |

`CreateTeam` body includes the first team-admin binding, the team's models, required tag values and,
when more than one provider exists, `identityProviderId`. A team missing a required tag is refused
with `ValidationError` naming the keys. An ephemeral team (`kind: ephemeral`) also needs `expiresAt`
(at most `teams.ephemeral_max_days` ahead), `teardownRule` (`at_expiry` \| `at_cap_or_expiry` \|
`at_work_complete`) and a lifetime `budget` in the same request; `kind` cannot change later.
`isolationTier` and `viewerKubectl` are guardrail fields (`teams:set-guardrails`).

### 4.3 Members and API keys

| Op | Method and path | Perm | CLI | SDK | Screen | P |
|---|---|---|---|---|---|---|
| `ListMembers` | `GET /v1/teams/{teamId}/members` | `members:read` | `members list-members` | `members.list()` | T6 | P0 |
| `AddMember` | `POST /v1/teams/{teamId}/members` | `members:write` | `members add-member` | `members.add()` | T6 | P0 |
| `UpdateMember` | `PATCH /v1/teams/{teamId}/members/{bindingId}` | `members:write` | `members update-member` | `members.update()` | T6 | P0 |
| `RemoveMember` | `DELETE /v1/teams/{teamId}/members/{bindingId}` | `members:write` | `members remove-member` | `members.remove()` | T6 | P0 |
| `ListApiKeys` | `GET /v1/teams/{teamId}/api-keys` | `api-keys:read` | `api-keys list-api-keys` | `apiKeys.list()` | T6 | P1 |
| `CreateApiKey` | `POST /v1/teams/{teamId}/api-keys` | `api-keys:write` | `api-keys create-api-key` | `apiKeys.create()` | T6 | P1 |
| `DeleteApiKey` | `DELETE /v1/teams/{teamId}/api-keys/{keyId}` | `api-keys:write` | `api-keys delete-api-key` | `apiKeys.delete()` | T6 | P1 |
| `ListServiceApiKeys` / `CreateServiceApiKey` / `DeleteServiceApiKey` | `/v1/admin/api-keys[/{keyId}]` (role `security_operator` only) | `admin:settings` *svc* | `admin list-api-keys` / `create-api-key` / `delete-api-key` | `admin.apiKeys.*` | settings | P2 |
| `ListSecurityOperators` / `AddSecurityOperator` / `RemoveSecurityOperator` | `/v1/admin/security-operators[/{bindingId}]` (users or IdP groups) | `admin:settings` *svc* | `admin list-security-operators` … | `admin.securityOperators.*` | settings | P2 |

`CreateApiKey` returns `secretKey` once; it is never returned again and never logged.

### 4.4 Agents

| Op | Method and path | Perm | CLI | SDK | Screen | P |
|---|---|---|---|---|---|---|
| `ListAgents` | `GET /v1/teams/{teamId}/agents` | `agents:read` | `agents list-agents` | `agents.list()` | T2 | P0 |
| `CreateAgent` | `POST /v1/teams/{teamId}/agents` | `agents:write` | `agents create-agent` | `agents.create()` | T3 | P0 |
| `GetAgent` | `GET /v1/teams/{teamId}/agents/{agentId}` | `agents:read` | `agents describe-agent` | `agents.get()` | T2 | P0 |
| `UpdateAgent` | `PATCH /v1/teams/{teamId}/agents/{agentId}` | `agents:write` | `agents update-agent` | `agents.update()` | T3 | P0 |
| `DeleteAgent` | `DELETE /v1/teams/{teamId}/agents/{agentId}` | `agents:write` | `agents delete-agent` | `agents.delete()` | T2 | P0 |
| `PauseAgent` / `ResumeAgent` / `RestartAgent` | `POST …/agents/{agentId}:pause` / `:resume` / `:restart` | `agents:write` | `agents pause-agent` / `resume-agent` / `restart-agent` | `agents.pause()` / `resume()` / `restart()` | T2 | P0 |
| `GetAgentStatus` | `GET …/agents/{agentId}/status` | `agents:read` | `agents get-agent-status` | `agents.getStatus()` | T2 | P0 |
| `ListAgentSnapshots` | `GET …/agents/{agentId}/snapshots` | `agents:read` | `agents list-snapshots` | `agents.snapshots.list()` | T3 | P0 |
| `CreateAgentSnapshot` | `POST …/agents/{agentId}/snapshots` | `agents:write` | `agents create-snapshot` | `agents.snapshots.create()` | T2 | P0 |
| `ListStorageClasses` | `GET /v1/storage-classes` | `models:read` | `agents list-storage-classes` | `storageClasses.list()` | T3 | P0 |

Agent spec fields (create and update): `name` (create only), `description`, `template`, `image`
(digest-pinned), `modelId`, `resources`, `iamIdentity` (`team_shared` \| `dedicated`), `volume`
{`sizeGiB` grow-only, `storageClass` create-only, `onDelete`, `snapshotSchedule`, `snapshotRetain`},
`secretBindings[]` {`secretId`, `delivery` `env` \| `file`, `target`}. The agent has no replica count.

### 4.4a Swarms: stages and pools

Ephemeral teams only (`409 Conflict` on a persistent team). Pool names share the team's agent names.

| Op | Method and path | Perm | CLI | SDK | Screen | P |
|---|---|---|---|---|---|---|
| `ListStages` … `DeleteStage` | `/v1/teams/{teamId}/stages[/{stageId}]` (`name`, `position`) | `pools:read` / `pools:write` | `pools list-stages` / `create-stage` / `update-stage` / `delete-stage` | `pools.stages.*` | P4 | P2 |
| `ListPools` | `GET /v1/teams/{teamId}/pools` | `pools:read` | `pools list-pools` | `pools.list()` | P4 | P2 |
| `CreatePool` | `POST /v1/teams/{teamId}/pools` | `pools:write` | `pools create-pool` | `pools.create()` | P4 | P2 |
| `GetPool` / `UpdatePool` / `DeletePool` | `GET`/`PATCH`/`DELETE …/pools/{poolId}` | `pools:read` / `pools:write` | `pools describe-pool` / `update-pool` / `delete-pool` | `pools.get()` / `update()` / `delete()` | P4 | P2 |
| `ScalePool` | `POST …/pools/{poolId}:scale` `{workers}` (0–200) | `pools:write` | `pools scale-pool` | `pools.scale()` | P4 | P2 |
| `PausePool` / `ResumePool` | `POST …/pools/{poolId}:pause` / `:resume` | `pools:write` | `pools pause-pool` / `resume-pool` | `pools.pause()` / `resume()` | P4 | P2 |
| `GetPoolStatus` | `GET …/pools/{poolId}/status` (desired, reporting, working, idle, impaired workers) | `pools:read` | `pools get-pool-status` | `pools.getStatus()` | P4 | P2 |
| `ListPoolHandoffs` / `PutPoolHandoffs` | `GET`/`PUT …/pools/{poolId}/handoffs` `{toPoolIds[]}` | `pools:read` / `pools:write` | `pools list-handoffs` / `put-handoffs` | `pools.handoffs.*` | P4 | P2 |
| `ListPoolSecretBindings` / `PutPoolSecretBindings` | `GET`/`PUT …/pools/{poolId}/secret-bindings` | `pools:read` / `pools:write` | `pools list-secret-bindings` / `put-secret-bindings` | `pools.secretBindings.*` | P4 | P2 |
| `ListPoolConfigValues` … `DeletePoolConfigValue` | `/v1/teams/{teamId}/pools/{poolId}/config-values[/{name}]` | `pools:read` / `pools:write` | `pools list-config-values` … | `pools.config.*` | P4 | P2 |
| `ListPoolExternalSystems` / `PutPoolExternalSystem` | `GET …/pools/{poolId}/external-systems`, `PUT …/{systemId}` `{enabled}` | `pools:read` / `pools:write` | `pools list-external-systems` / `put-external-system` | `pools.externalSystems.*` | P4 | P2 |
| `ListPoolRoleLinks` … `VerifyPoolRoleLink` | `/v1/teams/{teamId}/pools/{poolId}/role-links[/{linkId}][:verify]` (one `roleName`, one link per account) | `pools:read` / `pools:write` | `pools list-role-links` / `create-role-link` / `delete-role-link` / `verify-role-link` | `pools.roleLinks.*` | P4 | P2 |

Pool secrets are team secrets with `scope: pool` and `poolId` (managed path
`<prefix>/<namespace>/<pool>/<name>`), created through `CreateSecret`. Pool usage, activity, traffic and
audit records carry `poolId` and the worker pod name. Each handoff gets an SQS queue that the
reconciler creates; both pools receive its URL as an environment variable
(`AFS_HANDOFF_<TO_POOL>_QUEUE_URL` in the sender, `AFS_INBOX_QUEUE_URL` in the receiver) (D22).

### 4.5 Agent identity and AWS access

| Op | Method and path | Perm | CLI | SDK | Screen | P |
|---|---|---|---|---|---|---|
| `ListAgentRoleLinks` | `GET …/agents/{agentId}/role-links` | `identities:read` | `agents list-role-links` | `agents.roleLinks.list()` | T8 | P1 |
| `CreateAgentRoleLink` | `POST …/agents/{agentId}/role-links` | `identities:write` | `agents create-role-link` | `agents.roleLinks.create()` | T8 | P1 |
| `GetAgentRoleLink` | `GET …/role-links/{linkId}` (includes `trustPolicy` JSON) | `identities:read` | `agents describe-role-link` | `agents.roleLinks.get()` | T8 | P1 |
| `DeleteAgentRoleLink` | `DELETE …/role-links/{linkId}` | `identities:write` | `agents delete-role-link` | `agents.roleLinks.delete()` | T8 | P1 |
| `VerifyAgentRoleLink` | `POST …/role-links/{linkId}:verify` | `identities:write` | `agents verify-role-link` | `agents.roleLinks.verify()` | T8 | P1 |
| `ListAgentIdentities` | `GET …/agents/{agentId}/identities` | `identities:read` | `agents list-identities` | `agents.identities.list()` | T2 | P1 |
| `CreateAgentIdentity` / `DeleteAgentIdentity` | `POST` / `DELETE …/identities[/{identityId}]` | `identities:write` | `agents create-identity` / `delete-identity` | `agents.identities.create()` / `delete()` | T2 | P1 |

### 4.6 Secrets

| Op | Method and path | Perm | CLI | SDK | Screen | P |
|---|---|---|---|---|---|---|
| `ListSecrets` | `GET /v1/teams/{teamId}/secrets` | `secrets:read-metadata` | `secrets list-secrets` | `secrets.list()` | T4, V2 | P0 |
| `CreateSecret` | `POST /v1/teams/{teamId}/secrets` | `secrets:write` | `secrets create-secret` | `secrets.create()` | T4 | P0 |
| `GetSecret` | `GET …/secrets/{secretId}` | `secrets:read-metadata` | `secrets describe-secret` | `secrets.get()` | T4 | P0 |
| `UpdateSecret` | `PATCH …/secrets/{secretId}` | `secrets:write` | `secrets update-secret` | `secrets.update()` | T4 | P0 |
| `DeleteSecret` | `DELETE …/secrets/{secretId}` | `secrets:write` | `secrets delete-secret` | `secrets.delete()` | T4 | P0 |
| `PutSecretValue` | `PUT …/secrets/{secretId}/value` → 204 | `secrets:write` | `secrets put-secret-value` | `secrets.putValue()` | T4 | P0 |
| `RotateSecret` | `POST …/secrets/{secretId}:rotate` | `secrets:write` | `secrets rotate-secret` | `secrets.rotate()` | T4 | P1 |

`CreateSecret` body: `scope` (`team` \| `agent`), `agentId` (agent scope), `name`, `description`,
`externalSystemId` (optional), `value`. The value is sent once, passed to Secrets Manager and dropped.
No response, error, log line or audit record contains it. The server sets `secretsManagerPath`.
`DeleteSecret` on a bound secret → `409 Conflict` listing the agents.

### 4.7 Configuration values

| Op | Method and path | Perm | CLI | SDK | Screen | P |
|---|---|---|---|---|---|---|
| `ListNamespaceConfigValues` | `GET /v1/teams/{teamId}/config-values` | `config:read` | `teams list-config-values` | `config.namespace.list()` | T7 | P0 |
| `PutNamespaceConfigValue` | `PUT …/config-values/{name}` | `config:write` | `teams put-config-value` | `config.namespace.put()` | T7 | P0 |
| `DeleteNamespaceConfigValue` | `DELETE …/config-values/{name}` | `config:write` | `teams delete-config-value` | `config.namespace.delete()` | T7 | P0 |
| `ListAgentConfigValues` | `GET …/agents/{agentId}/config-values` (resolved, with `source`) | `config:read` | `agents list-config-values` | `config.agent.list()` | T7 | P0 |
| `PutAgentConfigValue` | `PUT …/agents/{agentId}/config-values/{name}` body `{source: literal\|namespace, value?}` | `config:write` | `agents put-config-value` | `config.agent.put()` | T7 | P0 |
| `DeleteAgentConfigValue` | `DELETE …/agents/{agentId}/config-values/{name}` | `config:write` | `agents delete-config-value` | `config.agent.delete()` | T7 | P0 |

### 4.8 External systems

| Op | Method and path | Perm | CLI | SDK | Screen | P |
|---|---|---|---|---|---|---|
| `ListTeamExternalSystems` | `GET /v1/teams/{teamId}/external-systems` (catalog + team-declared, with team state) | `external-systems:read` | `teams list-external-systems` | `externalSystems.team.list()` | T9 | P0 |
| `SetTeamExternalSystemState` | `PUT …/external-systems/{systemId}/state` `{enabled}` | `external-systems:write` | `teams set-external-system-state` | `externalSystems.team.setState()` | T9 | P0 |
| `DeclareTeamExternalSystem` | `POST …/external-systems` | `external-systems:write` + team `mayAddExternalSystems` | `teams declare-external-system` | `externalSystems.team.declare()` | T9 | P1 |
| `UpdateTeamExternalSystem` / `DeleteTeamExternalSystem` | `PATCH` / `DELETE …/external-systems/{systemId}` (team-declared only) | `external-systems:write` | `teams update-external-system` / `delete-external-system` | `…update()` / `delete()` | T9 | P1 |
| `ListAgentExternalSystems` | `GET …/agents/{agentId}/external-systems` (effective, with `disabledAt`) | `external-systems:read` | `agents list-external-systems` | `externalSystems.agent.list()` | T10 | P0 |
| `SetAgentExternalSystemState` | `PUT …/agents/{agentId}/external-systems/{systemId}/state` | `external-systems:write` | `agents set-external-system-state` | `externalSystems.agent.setState()` | T10 | P0 |

### 4.9 Budget, usage and reports

| Op | Method and path | Perm | CLI | SDK | Screen | P |
|---|---|---|---|---|---|---|
| `GetBudget` / `PutBudget` | `GET`/`PUT /v1/teams/{teamId}/budget` | `budgets:read` / `budgets:write` | `budgets get-budget` / `put-budget` | `budgets.get()` / `put()` | T5 | P0 |
| `GetUsage` | `GET …/usage?from&to&groupBy=agent\|model\|day` *CSV* | `usage:read` | `budgets get-usage` | `usage.get()` | T5 | P0 |
| `ListCosts` | `GET …/costs?from&to` (gateway and CUR by day) *CSV* | `usage:read` | `budgets list-costs` | `usage.listCosts()` | T5 | P1 |
| `GetTeamReport` | `GET …/reports/{usage\|costs\|activity\|traffic}` *CSV* | `reports:read` | `reports get-team-report` | `reports.team()` | T11 | P0 |
| `GetAgentReport` | `GET …/agents/{agentId}/reports/{kind}` *CSV* | `reports:read` | `reports get-agent-report` | `reports.agent()` | T12 | P0 |
| `GetServiceReport` | `GET /v1/reports/{kind}` *CSV* | `admin:reports` *svc* | `reports get-service-report` | `reports.service()` | S8, S9 | P0 |
| `ListReportSchedules` … `DeleteReportSchedule` | `GET`/`POST /v1/teams/{teamId}/report-schedules`, `PATCH`/`DELETE …/{scheduleId}` | `reports:schedule` | `reports list-report-schedules` … | `reports.schedules.*` | T11 | P1 |
| `ListCostTagStatus` | `GET /v1/admin/cost-tag-status` (per key: seen in CUR, first and last seen, AWS activation status) | `admin:cost-tag-status` *svc* | `admin list-cost-tag-status` | `admin.costTagStatus.list()` | S9 | P2 |

A report schedule has `name`, `report` (`usage` \| `costs` \| `activity` \| `traffic`), `query` (the
report query parameters below, stored), `cadence` (`daily` \| `weekly` \| `monthly`), `channelId` (one of
**the team's own** notification channels; a service-level channel → `ValidationError`), `format` (`csv`),
`enabled`, and read-only `nextRunAt`, `lastRunAt`, `lastStatus`, `lastError`.

Report query parameters: `from`, `to` (or `range=24h|7d|30d|90d|mtd`), `groupBy`
(`team|agent|model|system|day|hour|tag:<key>`), filters `teamId`, `agentId`, `modelId`, `systemId`,
`tag.<key>=<value>`, and in ephemeral teams `poolId` and `groupBy=pool`. Grouping by tag uses the tags in
effect when each record happened (TAG-6); a record missing a currently required key reports
`"(untagged)"` for that key. Traffic reports carry counts and bytes, never a cost. Response: `{"range": {...}, "groupBy": [...], "rows": [...], "totals": {...},
"notes": ["Spend with providers other than Bedrock is not included"]}`.

### 4.10 Delivery, notifications, audit and history

| Op | Method and path | Perm | CLI | SDK | Screen | P |
|---|---|---|---|---|---|---|
| `ListLogDestinations` … `DeleteLogDestination` | `/v1/teams/{teamId}/log-destinations[/{id}]` | `logs:read` / `logs:write` | `teams list-log-destinations` … | `logDestinations.*` | T1 | P1 |
| `ListNotificationChannels` … `DeleteNotificationChannel` | `/v1/teams/{teamId}/notification-channels[/{id}]` | `notifications:read` / `notifications:write` | `teams list-notification-channels` … | `notificationChannels.*` | T5 | P1 |
| `ListAuditEvents` | `GET /v1/teams/{teamId}/audit-events` *CSV* | `audit:read` | `audit list-audit-events` | `audit.list()` | T1 | P0 |
| `ListRevisions` / `GetRevision` | `GET /v1/teams/{teamId}/revisions[/{rev}]` | `revisions:read` | `teams list-revisions` / `describe-revision` | `revisions.list()` / `get()` | T1 | P0 |
| `RestoreRevision` | `POST …/revisions/{rev}:restore` (`dryRun` supported) | `revisions:restore` | `teams restore-revision` | `revisions.restore()` | T1 | P1 |

### 4.10a Work orders and swarm templates

| Op | Method and path | Perm | CLI | SDK | Screen | P |
|---|---|---|---|---|---|---|
| `ListWorkOrders` | `GET /v1/work-orders?status&severity&slaState&teamId` *CSV* | `work-orders:read` (security operators and service admins: all; teams: assigned or own repos) | `work-orders list-work-orders` | `workOrders.list()` | P3 | P2 |
| `CreateWorkOrder` | `POST /v1/work-orders` | `work-orders:write` | `work-orders create-work-order` | `workOrders.create()` | P3 | P2 |
| `GetWorkOrder` | `GET /v1/work-orders/{workOrderId}` (with repositories, progress counts, `slaState` and notifications) | `work-orders:read` | `work-orders describe-work-order` | `workOrders.get()` | P6 | P2 |
| `UpdateWorkOrder` | `PATCH /v1/work-orders/{workOrderId}` (title, SLA, cap, add repositories) | `work-orders:write` | `work-orders update-work-order` | `workOrders.update()` | P6 | P2 |
| `CancelWorkOrder` | `POST /v1/work-orders/{workOrderId}:cancel` `{reason}` | `work-orders:write` | `work-orders cancel-work-order` | `workOrders.cancel()` | P6 | P2 |
| `ListWorkOrderRepos` | `GET /v1/work-orders/{workOrderId}/repos` | `work-orders:read` | `work-orders list-repos` | `workOrders.repos.list()` | P6 | P2 |
| `UpdateWorkOrderRepo` | `PATCH /v1/work-orders/{workOrderId}/repos/{host}/{owner}/{repo}` `{status, prUrl?, prNumber?, detail?}` | `work-orders:report` (assigned team) or `work-orders:write` | `work-orders update-repo` | `workOrders.repos.update()` | P6 | P2 |
| `ListTeamWorkOrders` | `GET /v1/teams/{teamId}/work-orders` | `work-orders:read` | `work-orders list-team-work-orders` | `workOrders.listForTeam()` | T1 | P2 |
| `ListSwarmTemplates` … `DeleteSwarmTemplate` | `/v1/admin/swarm-templates[/{templateId}]` (`:enable` / `:disable`) | `admin:swarm-templates` *svc* (security operators may list) | `swarm-templates list-swarm-templates` / `create-…` / `describe-…` / `update-…` / `delete-…` | `swarmTemplates.*` | P5 | P2 |

`CreateWorkOrder` body: `cveId` (the `externalRef`, one open work order per CVE → `409 Conflict`),
`severity` (`critical` \| `high` \| `medium` \| `low`), `title`, `slaDueAt`, `templateId`, optional
`budgetUsd` (else the template's), and `repos[]` {`host`, `repo` (`owner/name`), `owningTeamId?`,
`owningContact?` (email)}; each repository needs at least one owner. AFS creates the remediation team
from the template and returns the work order with `teamId` once assigned. The same work order can
arrive as an EventBridge event `afs.work_order.requested` with `source_event_id`; duplicates are
ignored (D22).

### 4.11 Service administration

| Op | Method and path | Perm | CLI | SDK | Screen | P |
|---|---|---|---|---|---|---|
| `GetSettings` / `PutSetting` | `GET /v1/admin/settings`, `PUT …/{key}` | `admin:settings` | `admin get-settings` / `put-setting` | `admin.settings.*` | settings | P0 |
| `ListIdentityProviders` … `DeleteIdentityProvider` | `/v1/admin/identity-providers[/{id}]` | `admin:identity-providers` | `admin list-identity-providers` … | `admin.identityProviders.*` | settings | P0 |
| `ListServiceTags` / `PutServiceTag` / `DeleteServiceTag` | `GET /v1/admin/service-tags`, `PUT`/`DELETE …/{key}` | `admin:service-tags` | `admin list-service-tags` / `put-service-tag` / `delete-service-tag` | `admin.serviceTags.*` | S9 | P1 |
| `ListModels` | `GET /v1/models` | `models:read` | `models list-models` | `models.list()` | T3 | P0 |
| `ListAdminModels` / `CreateModel` / `UpdateModel` | `/v1/admin/models[/{modelId}]` | `admin:models` | `admin list-models` … | `admin.models.*` | S4 | P0 |
| `ListModelPrices` / `CreateModelPrice` | `/v1/admin/models/{modelId}/prices` | `admin:pricing` | `admin list-model-prices` / `create-model-price` | `admin.prices.*` | S4 | P0 |
| `ListModelPriceProposals` | `GET /v1/admin/model-price-proposals?status=pending` | `admin:pricing` | `admin list-price-proposals` | `admin.priceProposals.list()` | S4, S1 | P1 |
| `ApproveModelPriceProposal` / `RejectModelPriceProposal` | `POST …/{proposalId}:approve` / `:reject` `{note}` | `admin:pricing` | `admin approve-price-proposal` / `reject-price-proposal` | `…approve()` / `reject()` | S4 | P1 |
| `ListCostReconciliations` | `GET /v1/admin/cost-reconciliations?status=over_threshold` | `admin:reports` | `admin list-cost-reconciliations` | `admin.reconciliations.list()` | S1 | P1 |
| `ListCatalogSystems` … `DeleteCatalogSystem` | `/v1/admin/external-systems[/{systemId}]` (built-ins cannot be deleted) | `admin:external-systems` | `admin list-external-systems` … | `admin.externalSystems.*` | S7 | P0 |
| `ListStorageClassesAdmin` / `PutStorageClass` / `DeleteStorageClass` | `/v1/admin/storage-classes[/{name}]` | `admin:storage-classes` | `admin put-storage-class` … | `admin.storageClasses.*` | settings | P0 |
| `ListOrgAccounts` | `GET /v1/admin/org-accounts` | `admin:accounts` | `admin list-org-accounts` | `admin.orgAccounts.list()` | S6 | P1 |
| `ListAdminAuditEvents` | `GET /v1/admin/audit-events` *CSV* | `admin:audit` | `audit list-service-audit-events` | `admin.audit.list()` | S5 | P0 |
| `CreateExport` / `GetExport` | `POST /v1/exports`, `GET …/{exportId}` | `admin:export` | `admin create-export` / `describe-export` | `admin.exports.*` | export | P1 |
| `CreateImport` | `POST /v1/imports` (`dryRun`, account map) | `admin:export` | `admin create-import` | `admin.imports.create()` | export | P1 |
| `GetHealth` / `GetReadiness` | `GET /healthz`, `/readyz` | none | — | `health.get()` | — | P0 |

## 5. Resource shapes (wire, abbreviated)

Fields marked † are read-only. All resources also carry `id`†, `version`†, `createdAt`†, `createdBy`†,
`updatedAt`† and, for desired state, `generation`† and `status`†.

```yaml
Team:        {slug, displayName, description, kind: persistent|ephemeral, state†: active|suspended|deleting|deleted,
              namespace†, costCenter, ownerEmail, maxBudgetUsd, quotas{cpu,memory,pods,storage},
              isolationTier: shared|dedicated, viewerKubectl, expiresAt?, teardownRule?: at_expiry|at_cap_or_expiry|at_work_complete,
              tornDownAt†?, teardownReason†?, identityProviderId?, allowedAwsAccounts[], mayManageAwsAccounts,
              mayAddExternalSystems}
TeamTags:    {tags: [{key, value?, source†: system|service|team|service_default|missing}]}       # PUT sends team-owned keys only
Member:      {role: team_admin|team_viewer, subjectType: user|group, userId?, email†?, groupName?}
ApiKey:      {name, role, keyPrefix†, expiresAt (≤ 90 days), lastUsedAt†, secretKey† (create response only)}
Agent:       {name, description, template, image, modelId, resources{cpu,memory}, iamIdentity, iamRoleArn†,
              volume{sizeGiB, storageClass, onDelete: snapshot_then_delete|delete|retain, snapshotSchedule: off|daily|weekly, snapshotRetain},
              secretBindings[{secretId, delivery: env|file, target}], paused†}
RoleLink:    {profileName, roleArn, accountId†, maxSessionSeconds, externalId†, status†: pending_trust|verified|failed|disabled,
              lastVerifiedAt†, trustPolicy†}
Stage:       {name, position, description}
Pool:        {name, description, stageId?, template, image, persona?, modelId, workers (0..200), resources{cpu,memory},
              scratchSizeGiB (1..500), sharedVolume: none|efs, state†: enabled|paused|deleting|deleted, handoffs†[poolId]}
PoolRoleLink: {roleName, accountId, profileName, roleArn†, externalId†, maxSessionSeconds, status†, lastVerifiedAt†}
SwarmTemplate: {name, description, kind: cve_remediation|general, spec{stages[], pools[], handoffs[], secrets[], configValues[]},
              budgetUsd, ttlHours, teardownRule, enabled}
WorkOrder:   {kind: cve_remediation|general, cveId?, severity, title, source†: api|eventbridge, templateId, budgetUsd, slaDueAt,
              status†: open|assigned|in_progress|pr_opened|done|failed|cancelled, teamId†?, assignedAt†?, completedAt†?,
              slaState†: on_track|due_soon|breached|met|missed, progress†{repos, prsOpen, prsMerged, notAffected, failedOrSkipped, remaining}}
WorkOrderRepo: {host, repo, owningTeamId?, owningContact?, status: pending|in_progress|pr_opened|merged|not_affected|failed|skipped,
              prUrl?, prNumber?, detail?, mergedAt†?, notifications†[{kind, recipient, sentAt}]}
ReportSchedule: {name, report, query{}, cadence, channelId, format: csv, enabled, nextRunAt†, lastRunAt†, lastStatus†, lastError†}
CostTagStatus: {key, seenInCur, firstSeenAt, lastSeenAt, awsStatus: active|inactive|unknown, checkedAt}
Secret:      {scope: team|agent|pool, agentId?, poolId?, name, description, externalSystemId?, secretsManagerPath†, secretsManagerArn†,
              versionId†, lastChangedAt†, rotation{enabled, days}, boundTo†[agentId]}               # no value field, ever
ConfigValue: {name, value?, source: literal|namespace, resolvedValue†, usedBy†[agentId]}
ExternalSystem: {slug, name, category, description, docsUrl, endpoints[], enabled, builtin†, owner?, purpose?,
              scope†: service|team, teamState†: on|off, disabledAt†: service|team|agent|null, unmetered†}
Budget:      {period: monthly|lifetime, amountUsd, thresholds[], onExhaust: block|notify, expiresAt?,
              spentUsd†, reservedUsd†, percentUsed†, forecastUsd†, projectedCapAt†}
ServiceTag:  {key, mode: fixed|required, value?, defaultValue?, allowedValues?[], description}
IdentityProvider: {kind: okta|entra_id, name, issuerUrl, clientId, clientSecretArn?, groupsClaim, isDefault, enabled}
PriceProposal: {modelId, effectiveFrom, inputUsdPerMtok, outputUsdPerMtok, cacheReadUsdPerMtok, cacheWriteUsdPerMtok,
              status†: pending|approved|rejected|superseded, fetchedAt†, decidedBy†, decidedAt†, note}
Me:          {principal{id, type: user|api_key, email?, name?}, serviceAdmin, securityOperator, teams[{teamId, slug, role, permissions[]}]}
```

## 6. Errors

Body: `{"code": "…", "message": "…", "requestId": "…", "details": {…}}`. `message` is for people and may
change; clients branch on `code` only. No error contains a secret value, token or API key.

| HTTP | `code` | When | Database origin (see [database contract](database-contract.md) §6) |
|---|---|---|---|
| 400 | `ValidationError` | Malformed or out-of-range input; `details.fields[]` lists `{field, reason}` | `23514`, `23502`, `22xxx` |
| 401 | `Unauthenticated` | Missing, expired or unknown credential | — |
| 403 | `AccessDenied` | Valid caller without the permission; `details.requiredPermission` | `42501` |
| 404 | `NotFound` | No such resource, **or** a resource in a team the caller cannot see (never reveals existence) | RLS hides the row |
| 409 | `Conflict` | Duplicate name, idempotency body mismatch, dependent objects exist, invalid state transition | `23505`, `23503` (on delete), `55000` |
| 412 | `PreconditionFailed` | `If-Match` does not match `version` | — |
| 422 | `BudgetExceeded` | Returned by the gateway to agents; never by `afs-api` | `reserve_spend` false |
| 428 | `PreconditionRequired` | `If-Match` missing on update or delete | — |
| 429 | `Throttled` | Rate limit; `Retry-After` | — |
| 500 | `InternalError` | Anything else; logged with `requestId` | `40001` after retries, others |
| 503 | `Unavailable` | Dependency down (database, Secrets Manager); safe to retry with backoff | — |

CLI rendering: `An error occurred (<code>) when calling the <operationId> operation: <message>`, exit
254. SDK: `AfsError` with `code`, `status`, `requestId`, `details`, and helpers `isAccessDenied`,
`isNotFound`, `isConflict`, `isPreconditionFailed`.

## 7. Events (EventBridge, from the outbox)

Source `afs`, `detail-type` = event type, `detail` = `{id, occurredAt, teamId, agentId?, actor, data}`.
Consumers must be idempotent on `id`.

| Type | Emitted by | When |
|---|---|---|
| `team.created`, `team.updated`, `team.suspended`, `team.resumed`, `team.deleted`, `team.tags_changed` | api | Team mutations |
| `team.status_changed`, `agent.status_changed` | reconciler | Phase change |
| `agent.created`, `agent.updated`, `agent.deleted`, `agent.paused`, `agent.resumed`, `agent.restarted` | api | Agent mutations |
| `secret.created`, `secret.rotated`, `secret.deleted` | api | No value in the event |
| `budget.threshold_crossed`, `budget.exhausted`, `budget.reset` | gateway, reconciler | Once per period per threshold |
| `cost.variance_detected`, `pricing.proposal_created`, `pricing.proposal_decided` | billing, api | BUD-6, BUD-9 |
| `drift.corrected` | reconciler | Manual change reverted |
| `egress.denied_spike` | reconciler collectors | RPT-6. Agent sign-ins go to team log delivery only, never to events (D17) |
| `role_link.verified`, `role_link.failed` | reconciler | AGT-10 |
| `team.teardown_started`, `team.torn_down` | reconciler | TEAM-7; `data.reason` = `expired` \| `cap_reached` \| `work_complete` \| `manual` |
| `pool.created`, `pool.updated`, `pool.scaled`, `pool.deleted`, `pool.status_changed` | api, reconciler | AGT-8 |
| `report.delivered`, `report.failed` | billing | RPT-8 |
| `work_order.created`, `work_order.assigned`, `work_order.repo_updated`, `work_order.pr_opened`, `work_order.merged`, `work_order.sla_warning`, `work_order.sla_breached`, `work_order.completed`, `work_order.failed`, `work_order.cancelled` | api, reconciler | WO-1 to WO-5; owners notified once per event |
| `cost_tags.not_seen` | billing | TAG-7 |

## 8. Change process

1. Propose the change in this document (or directly in `openapi.yaml` once it holds the operation) in
   a `-restapi` PR, labelled `contract`.
2. Additive changes merge with the handler. Breaking changes need a new path version and an ADR in the
   root.
3. After merge, `-website` regenerates `packages/sdk/src/generated/` and `-cli` regenerates its client,
   each in its own PR referencing the `-restapi` tag.
4. A contract test in each consumer replays the OpenAPI examples; CI fails on drift.
