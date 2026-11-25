# Status: team model gateway (1.2.0)

**Built.** Release 1.2.0 merged in every code repository on 2026-11-25 (`-website` on 2026-11-25 after J approved the visual
baselines); J pushes the tags. Progress: 100% for the root and all four children.

| Phase | State |
|---|---|
| 0 Research (PRD) | Complete: PRD approved, completeness review added Appendix D (2026-11-25) |
| 1 Specification | Complete: contracts gateway v1.2.0, API v1.5.0, database v1.5.0; ADR-018 |
| 2 to 4 | Complete per repository (each child's `specs/261125-model-endpoint-gateway/`) |
| 5 Implementation | `-db` done; `-restapi` done; `-cli` done; `-website` done (PR #14, merged a05f8ab) |
| 6 Completion | Complete for the root: contracts amended after the build, PRD status and §16, README and AGENTS tables, solution design, diagrams, `skills/` CLI entry, ADR-018 |

## Builds and tag targets

| Repository | PR | Merge commit (tag target for `v1.2.0`) | Notes |
|---|---|---|---|
| `-db` | #23 | `debc7d9d28fd0bf653b7489b8c8d3847a2412f22` | Migrations 000001–000023 (000024 on `main` belongs to 1.3.0) |
| `-restapi` | #11 (contract) | `7d48ea7` | OpenAPI v1.5.0, 221 operations (194 + 27); `api/contract/ROOT_REF` pin |
| `-restapi` | #14 (implementation) | `a46fa09b1d343525e4a791b099f3d4cf26118979` | Team gateway, reconciler, billing CronJobs; child ADR-031 to ADR-034. The tree also carries the v1.6.0 MCP operations (55, answering `501` until 1.3.0) |
| `-cli` | #12 | `bd20ad064864e831ecade963202244b4fd7e7eac` | `model-endpoints` (23 commands) plus 4 in `teams` and `reports`; 219 commands for 221 operations |
| `-website` | #14 | `a05f8abeea6168ff52a9c96b58ec516130cd2c8f` | `@afs/sdk` and console 1.2.0: SDK regenerated from 1.5.0, screens 56 to 68a; J approved the 14 new baselines and the 45 regenerated for the new nav |

## Root tasks

| Task | State |
|---|---|
| MEG-ROOT-1 to 3: contracts | Done (v1.5.0 / v1.2.0); amended after the build: API CD-53 to CD-60 (27 operations, `GetTeamInferenceReport`, routes in `models`), database CD-61 to CD-66, gateway CD-67 and CD-68 |
| MEG-ROOT-4: this spec, ADR-018 | Done; ADR-018 records what was built |
| MEG-ROOT-5: solution design, README, diagrams, `skills/` | Done: `architecture-overview` updated, `model-gateway` added |
| PRD corrections | Done: D.3.4 permissions (`admin:pricing`), separate team inference report, routes in `models`, US-68, §8.2, §11.1 |

## Deferred

- Pod Identity association for each team gateway ServiceAccount (Terraform per team for now).
- Live Azure and Google federation and token acquisition.
- Live Azure Cost Management and BigQuery billing fixtures (MEG-OQ-14).
- OpenRouter history for past days (no provider API).
- The reconciler writing `endpoint_credentials.status`.
- Local envtest runs of the reconciler (CI runs them).
- Real AWS, EKS, Azure and Google testing (J's cloud access).
- Contract gaps raised by the console build (API CD-60): *Test connection*, per-route agents and spend, recent provider
  changes, gateway URL and state.

## Follow-ups in children

Diagram copies refreshed: `-db` #27, `-restapi` #16 (also embeds `model-gateway.svg`), `-cli` #13. The `-website`
copy of `architecture-overview.svg` is still to refresh.
