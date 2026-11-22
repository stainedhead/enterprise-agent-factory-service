# Contributing to the Enterprise Agent Factory Service

Thank you for helping. AFS is five repositories that ship as one product. This guide covers what is common
to all of them; each repository's `AGENTS.md` has its own rules, toolchain and quality gate.

## Find where the change belongs

| You want to change | Repository | Notes |
|---|---|---|
| Requirements, cross-repo design, contracts, diagrams, UI mockups | this root | Documentation only; no code |
| Tables, roles, row-level security, migrations | [-db](https://github.com/stainedhead/enterprise-agent-factory-service-db) | A new migration; merged migrations are never edited |
| REST API, RBAC, reconciler, gateway, billing | [-restapi](https://github.com/stainedhead/enterprise-agent-factory-service-restapi) | `api/openapi.yaml` changes in the same PR as the handler |
| The `afs` command line | [-cli](https://github.com/stainedhead/enterprise-agent-factory-service-cli) | Commands are generated from the pinned contract |
| `@afs/sdk` or the web console | [-website](https://github.com/stainedhead/enterprise-agent-factory-service-website) | The SDK is generated from the pinned contract |

A change that crosses a contract goes in order: **contract first** (root `docs/contracts/`), then the
producer (`-db` for the database contract, `-restapi` for the API and gateway contracts), then the consumers
in their own PRs. See [repositories and contracts](docs/diagrams/repository-map.svg).

## Set up

Clone the set side by side ([getting started](user-docs/getting-started.md)):

```bash
git clone https://github.com/stainedhead/enterprise-agent-factory-service.git
cd enterprise-agent-factory-service
for r in db restapi cli website; do
  git clone https://github.com/stainedhead/enterprise-agent-factory-service-$r.git
done
```

Toolchains: Go 1.27 and `make` for `-db`, `-restapi` and `-cli` (PostgreSQL 17 or Docker for database
integration tests); Bun 1.4 for `-website`.

## Work spec first

Every repository uses the `dev-flow` workflow from
[shared-plugins](https://github.com/stainedhead/shared-plugins):

1. **PRD.** Each repository has a PRD with user stories and acceptance criteria that refine the
   [root PRD](enterprise-agent-factory-service-initial-PRD.md).
2. **Spec.** A feature gets a directory `specs/YYMMDD-<feature>/` with `spec.md`, `plan.md`, `tasks.md` and
   `status.md`. A feature that touches more than one repository gets its spec here, in the root `specs/`.
3. **Status.** Update `status.md` after every task. It is the single source of truth for progress.
4. **Archive.** When `status.md` is at 100 %, the spec moves to `specs/archive/`.

With Claude Code:

```
/plugin marketplace add https://github.com/stainedhead/shared-plugins
/plugin install dev-flow
/plugin install repo
```

## Test first

All code repositories follow Red, Green, Refactor. Every authorization rule has a test for the denied case,
every database constraint a test for the rejected case, and every console permission a disabled-control test.
Coverage floors: 90 % on `domain`, `usecase` and `authz` (`-restapi`), `migrate` (`-db`), `internal/...`
(`-cli`), and the console's `domain` and `application` layers (`-website`).

## Pass the gate

| Repository | Gate |
|---|---|
| -db | `make gate`, then `make db-up && make test-db` |
| -restapi | `make gate` (tidy, fmt, vet, contract checks, golangci-lint, race tests, build) |
| -cli | `make gate` (tidy, contract and generate checks, fmt, vet, lint, race tests, coverage, build) |
| -website | `bun run gate` (frozen install, contract and codegen checks, Biome, `tsc`, Vitest coverage, build, size) |
| root | No CI. Keep links honest and run the diagram renderer if you change a diagram (below) |

## Non-negotiables

- **The API is the security boundary.** Clients use `GET /v1/me` for UX only.
- **No secret values** in the database, logs, URLs, browser storage or shell history.
- **Team isolation** at every layer: namespace, IAM, secret path, row-level security, budget, logs.
- **No credentials, AWS account ids or tenant identifiers** in any repository.
- **Clean Architecture** in every code repository; dependency rules are enforced by tests.

## Diagrams and screenshots

- Architecture diagrams are generated: edit `docs/diagrams/source/<name>.mjs`, then run
  `node docs/diagrams/source/render.mjs` (Node 22 and Playwright). Commit the `.mjs`, `.svg` and `.png`
  together. Child repositories keep copies of the SVGs they show; refresh them when you change one.
- Console screenshots come from the website's Playwright suite:
  `bun run --filter @afs/console docs:screenshots` in `-website`.
- UI mockups live in `docs/ui/` with HTML sources in `docs/ui/source/`.

## Pull requests

- Branch from `main`, keep one purpose per PR, and reference the spec directory in commit messages.
- Fill in what changed, why, and how it was tested. CI must be green.
- In the root repository, check nothing from a child is staged: `git ls-files -s` shows no `160000` entries.
- Be kind in review. Critical and important findings (security, isolation, authorization, data loss) are
  fixed before merge.

## License

By contributing you agree that your contributions are licensed under the [MIT License](LICENSE).
