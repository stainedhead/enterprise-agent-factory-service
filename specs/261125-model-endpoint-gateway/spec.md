# Spec: team model gateway (release 1.2.0, cross-repo)

Source: [model-endpoint-gateway-PRD.md](../../model-endpoint-gateway-PRD.md), approved for build by J on 2026-11-25.
Requirements, stories and test cases are in the PRD (Appendix B, C and D); this spec tracks the cross-repo order and
the contracts.

| Repository | Spec | Requirements | Contract |
|---|---|---|---|
| root | this directory | MEG-ROOT-1 to 5 | gateway v1.2.0, API v1.5.0, database v1.5.0, ADR-018 |
| `-db` | `specs/261125-model-endpoint-gateway/` | MEG-DB-1 to 7 | provides database v1.5.0 (000023) |
| `-restapi` | `specs/261125-model-endpoint-gateway/` | MEG-GW, MEG-RC, MEG-BL, MEG-API | provides API v1.5.0 and gateway v1.2.0 |
| `-cli` | `specs/261125-model-endpoint-gateway/` | MEG-CLI-1 to 4 | consumes API v1.5.0 |
| `-website` | `specs/261125-model-endpoint-gateway/` | MEG-WEB-1 to 6 | consumes API v1.5.0 |

Order: contracts (root) → `-db` → `-restapi` → `-cli` and `-website` → root docs. Release 1.1.0 is not changed. Real
AWS, EKS, Azure and Google checks are deferred until J has cloud access (J, 2026-11-25); fakes and recorded fixtures
stand in.
