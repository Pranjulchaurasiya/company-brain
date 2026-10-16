# Company Brain

Company Brain is an AI company whose employee-agents answer questions and complete work across connected company context using a shared FalkorDB graph. The hackathon MVP demonstrates the general workflow through one Payments release-readiness example; Payments is demo data, not the product boundary.

The system connects people, teams, projects, documents, tickets, chats, and decisions. Employee-agents use that context to answer questions and get work done across it: plan, communicate, delegate, create or update deliverables, review results, and record outcomes. FalkorDB is the canonical source of company state.

The hackathon demo is reviewer-ready: it opens to a preloaded synthetic company workspace, requires no login or OAuth, and labels Slack/GitHub-style data and writes as simulated. The whole project is being built in Google Antigravity; see [BUILDING_WITH_ANTIGRAVITY.md](BUILDING_WITH_ANTIGRAVITY.md) for the implementation contract.

## Product promise

Give the company a goal. Its employees should be able to understand the context, make a plan, coordinate the work, explain their decisions, and show the sources behind their answers.

## Documents

- [PRD.md](PRD.md) — product scope and requirements
- [ARCHITECTURE.md](ARCHITECTURE.md) — system design
- [DATA_MODEL.md](DATA_MODEL.md) — FalkorDB graph schema
- [AGENTS.md](AGENTS.md) — employee roles and collaboration protocol
- [RULES.md](RULES.md) — safety and operating rules
- [TASKS.md](TASKS.md) — implementation roadmap
- [EVALUATION.md](EVALUATION.md) — quality and hackathon evaluation
- [CONTRIBUTING.md](CONTRIBUTING.md) — development conventions
- [BUILDING_WITH_ANTIGRAVITY.md](BUILDING_WITH_ANTIGRAVITY.md) — build workflow and coding-agent instructions

## Non-negotiable principle

FalkorDB is the canonical company state. Local files, prompts, caches, and generated graph exports are inputs or temporary artifacts, never the final source of truth.
