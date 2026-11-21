# Contracts between layers

AFS is built in four repositories that change independently. Two contracts keep them compatible. Each
repository PRD names the contracts it provides and consumes, and its acceptance criteria include
conformance tests against them.

```
 -website (@afs/sdk, console)      -cli (afs)
            │                          │
            └──────── API contract ────┘          api-contract.md  (OpenAPI: -restapi/api/openapi.yaml)
                          │
                  -restapi (afs-api, afs-reconciler, afs-gateway, afs-billing)
                          │
                  Database contract                database-contract.md (dictionary: -db/docs/data-model.md)
                          │
                  -db (migrations, roles, RLS)
```

| Contract | Provider | Consumers | Source of truth | Conformance |
|---|---|---|---|---|
| [Database contract](database-contract.md) | `-db` | `-restapi` | Migrations at a `-db` tag; dictionary in `-db/docs/data-model.md` | `-db` integration tests; `-restapi` repository tests against the pinned tag |
| [API contract](api-contract.md) | `-restapi` | `-cli`, `-website` | `-restapi/api/openapi.yaml`, built from this document | `-restapi` handler tests per operation and role; generated clients plus contract tests in `-cli` and `-website` |

Rules:

- A change to a contract lands in the provider first, in the same PR as the code, and is announced to
  consumers by the provider's release tag.
- Additive changes are minor. Breaking changes need an ADR in this root and a new version (a new `-db`
  expand/contract cycle, or `/v2` paths).
- The permission catalog (API contract §3) is mirrored exactly by `-website/apps/console/src/domain/permission.ts`.
- Repository PRDs: [-db](https://github.com/stainedhead/enterprise-agent-factory-service-db/blob/main/enterprise-agent-factory-service-db-PRD.md),
  [-restapi](https://github.com/stainedhead/enterprise-agent-factory-service-restapi/blob/main/enterprise-agent-factory-service-restapi-PRD.md),
  [-cli](https://github.com/stainedhead/enterprise-agent-factory-service-cli/blob/main/enterprise-agent-factory-service-cli-PRD.md),
  [-website](https://github.com/stainedhead/enterprise-agent-factory-service-website/blob/main/enterprise-agent-factory-service-website-PRD.md).
