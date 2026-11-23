# AGENTS.md

Rules and context for agents (and contributors) working in this directory.

## What this directory is
This is the **root repository for the Enterprise Agent Factory Service (AFS)**. It is documentation
only: it holds the product requirements, the cross-repo design, the UI mockups and cross-repo specs, and
exists so the independent child repositories below can be discovered, understood and worked on as one
product. It contains no source code, no build and no tests. See [INTENT.md](INTENT.md) for why it exists
and [enterprise-agent-factory-service-initial-PRD.md](enterprise-agent-factory-service-initial-PRD.md)
for what is being built.

Each child is a **separate git repository** that lives in a sub-directory of this one when cloned. They
are **not** tracked here: `.gitignore` ignores every top-level directory except an explicit allowlist
(`.github/`, `docs/`, `user-docs/`, `skills/`, `specs/`). Do not add submodules, subtrees or copies.

## Child repositories
Sub-directory names match the repository names. Clone each one next to this file:
`git clone https://github.com/stainedhead/<name>.git`.

| Directory | Language / kind | Purpose | Status |
|---|---|---|---|
| `enterprise-agent-factory-service-db/` | SQL, Go 1.27 | PostgreSQL schema and migrations, roles and row-level security, `afs-migrate`, Go module embedding the migrations | Feature complete (migrations 000001–000022); release 1.1.0, shared with `-restapi` (lockstep) |
| `enterprise-agent-factory-service-restapi/` | Go 1.27 | `afs-api` (REST, RBAC, audit), `afs-reconciler`, `afs-gateway`, `afs-billing`, `afs-edge`; owns `api/openapi.yaml` | Feature complete; release 1.1.0 (API 1.4.0), lockstep with `-db` |
| `enterprise-agent-factory-service-cli/` | Go 1.27 | `afs` CLI, AWS CLI conventions | Feature complete; release 1.1.0 |
| `enterprise-agent-factory-service-website/` | TypeScript 7 (Bun workspace) | `@afs/sdk` accelerator SDK (`packages/sdk`) and the web console (`apps/console`) | Feature complete; release 1.1.0 |

All remotes are `github.com/stainedhead/<name>`. When a repository is added or changes status, update
this table and the README table in the same change.

## How they relate
```
-website apps/console ──uses──► -website packages/sdk (@afs/sdk) ──HTTPS──┐
-cli (afs) ──HTTPS────────────────────────────────────────────────────────┤
                                                                          ▼
                                     -restapi afs-api (RBAC, audit, OpenAPI contract)
                                                │ writes desired state
                                                ▼
     -db migrations (imported as a Go module) ─► RDS PostgreSQL ◄── reads ── -restapi afs-reconciler ──► EKS + AWS
                                                ▲
             agents in team namespaces ──► -restapi afs-gateway (metered, capped) ──► Bedrock
```
- **The REST API is the security boundary.** RBAC is enforced in `afs-api`. The CLI and console only
  shape the UX from `GET /v1/me`; they never stand in for the API's decision.
- **The OpenAPI document is the contract.** It lives at `enterprise-agent-factory-service-restapi/api/openapi.yaml`.
  An API change lands there first; `@afs/sdk` and the CLI follow in their own PRs.
- **The schema has one home.** Only `-db` changes tables. `-restapi` depends on a tagged `-db` release
  and runs its migrations through the `migrate` package.
- **Shared contracts** between layers live in `docs/contracts/`: the database contract (`-db` → `-restapi`),
  the API contract (`-restapi` → `-cli`, `-website`) and the gateway contract (`-restapi` `afs-gateway` →
  agents and the Agentic Teammates runtime). Each child has its own PRD
  (`<repo-name>-PRD.md`) with user stories and acceptance criteria that refine the root PRD's stories.
- **Cross-repo design decisions** are recorded in this root (`docs/solution-design.md`,
  `docs/architectural-decision-record.md`). Single-repo decisions go in that repository's `docs/`.

## Rules for working here
- **Commit child changes in the child**, never in this root.
- **Only root-level material is committed here:** `README.md`, `INTENT.md`, `AGENTS.md`, `CLAUDE.md`,
  `CONTRIBUTING.md`, `LICENSE`, PRDs (`*-PRD.md`), `.gitignore`, `.github/` and anything under `docs/`, `user-docs/`, `skills/`
  or `specs/`. If you add a new top-level directory that belongs to this repo, add it to the allowlist in
  `.gitignore`.
- **Before committing, check nothing from a child is staged:** `git ls-files -s` must show no mode
  `160000` entries and no child repository paths.
- **Do not duplicate child documentation.** Summarize in one place and link to the child.
- **Keep links honest.** Only link to a remote that exists.
- **UI mockups** live in `docs/ui/` (PNG) with HTML sources in `docs/ui/source/`. Regenerate the PNGs when
  a source changes, and keep the PRD's screen list in step.
- **Architecture diagrams** live in `docs/diagrams/` (SVG and PNG) with their sources in
  `docs/diagrams/source/`. Edit the source and re-render (`node docs/diagrams/source/render.mjs`); never hand-edit
  an SVG. Child READMEs embed copies under their own `docs/images/`; refresh those copies when a diagram changes.
- **Screenshots** in `docs/images/screenshots/` are real captures of the console from the `-website` Playwright
  suite (`docs:screenshots`), not mockups.
- **`user-docs/` rule.** `user-docs/` holds only files that help someone adopt, install and use the set as
  a whole. It is not for design, requirements or process material, and it must not link into `specs/`.
- **`skills/` rule.** `skills/` holds agent skill documents for agent-facing tools in this set (the `afs`
  CLI first), named `<repo-name>.md`. Each must carry an honest status banner until a release exists.
- **Specs here are cross-repo only.** A feature that touches more than one child gets its spec in this
  root's `specs/`; each child's tasks reference it.
- Never put credentials, tokens, AWS account ids or tenant identifiers in this repository.

## Dev-Flow Skills

The following skills are available for the developer workflow. Invoke them with the listed slash command.

| Skill | Invocation | Purpose |
|---|---|---|
| `init-dev-flow` | `/init-dev-flow` | One-time repo setup; updates AGENTS.md |
| `create-prd` | `/create-prd [title]` | Interactive PRD authoring; writes to repo root |
| `review-prd` | `/review-prd [file]` | PRD quality review |
| `create-spec` | `/create-spec [prd-file]` | Spec creation from PRD; YYMMDD-prefixed directory |
| `review-spec` | `/review-spec [spec-dir]` | Spec quality review |
| `archive-spec` | `/archive-spec [spec-dir]` | Move completed spec to specs/archive/ |
| `implm-frm-prd` | `/implm-frm-prd [prd-file]` | Implement from PRD (11 steps) |
| `implm-frm-change-dtls` | `/implm-frm-change-dtls [ticket-or-desc]` | Implement from ticket or description (12 steps) |
| `implm-from-spec` | `/implm-from-spec [spec-dir]` | Full 11-step orchestrated implementation |
| `create-review` | `/create-review` | Code and design review artifact |
| `review-code` | `/review-code` | Code review of current branch |
| `write-flow-analys` | `/write-flow-analys [spec-dir]` | Process analysis report (final step of implm-from-spec) |

## Feature Specification Workflow

### Specs Directory Structure

All feature development uses the `specs/` directory for planning and tracking. Each feature gets its own subdirectory named `YYMMDD-<feature-name>/`.

**Directory Structure:**
```
specs/
└── YYMMDD-<feature-name>/
    ├── spec.md                  # Feature specification and requirements
    ├── status.md                # **CRITICAL**: Phase progress tracking (update after each task)
    ├── plan.md                  # Implementation plan and architecture decisions
    ├── tasks.md                 # Task breakdown and progress tracking
    ├── research.md              # Research findings, API docs, examples
    ├── data-dictionary.md       # Data structures, types, schemas
    ├── architecture.md          # System architecture and component design
    └── implementation-notes.md  # Implementation details, gotchas, decisions
```

### Progressive Documentation Build

Documents are created progressively as the feature develops:

**Phase 0: Initial Research (PRD/Feature Research)**
- Input: Product Requirement Document, RFC, or feature research
- Purpose: Understand the problem, gather requirements, identify constraints
- **Update status.md**: Mark Phase 0 as "In Progress"

**Phase 1: Specification (spec.md)**
- Define what the feature does, user requirements, acceptance criteria, goals and non-goals
- **Update status.md**: Mark Phase 0 complete, Phase 1 in progress

**Phase 2: Research & Data Modeling (research.md, data-dictionary.md)**
- Gather documentation, explore existing code, define domain entities and data structures
- **Update status.md**: Mark Phase 1 complete, Phase 2 in progress

**Phase 3: Architecture & Planning (architecture.md, plan.md)**
- Design implementation approach, identify affected layers, document component architecture
- **Update status.md**: Mark Phase 2 complete, Phase 3 in progress

**Phase 4: Task Breakdown (tasks.md)**
- Break down work into concrete, testable tasks with dependencies and estimates
- **Update status.md**: Mark Phase 3 complete, Phase 4 in progress

**Phase 5: Implementation (code + implementation-notes.md)**
- Follow TDD (Red-Green-Refactor), record decisions, document edge cases
- **Update status.md**: After EACH task completion — MANDATORY

**Phase 6: Completion & Archival**
- Update product documentation, move spec to `specs/archive/`, capture lessons learned
- **Verify status.md**: Must show 100% completion before archiving

**MANDATORY**: Update `status.md` after completing each task or phase. This file is the single source of truth for progress tracking.

### Specs Workflow Rules

- **Create the spec directory** before starting any new feature work
- **Update progressively** — specs are living documents, not written once
- **Update status.md ALWAYS** after completing each task, phase, or milestone — this is MANDATORY
- **Reference from commits** — link to the spec directory in commit messages
- **Archive completed specs** — move to `specs/archive/` when 100% complete in status.md
- **Version control** — commit specs alongside code for team visibility
