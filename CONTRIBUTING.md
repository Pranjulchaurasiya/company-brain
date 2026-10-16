# Contributing

## Development principles

- Keep FalkorDB central.
- Prefer small, typed, testable employee tools.
- Keep employee prompts and SOPs versioned as files.
- Store durable state in FalkorDB, not process memory.
- Make source provenance a first-class field.
- Add a test for every new graph query and tool action.
- Keep dangerous actions behind approval gates.
- Keep the judging workflow one-click and independent of login, OAuth, and third-party availability.
- Mark all synthetic connector data and simulated writes visibly.
- Keep company workflows reusable; demo names such as Payments must not become product-specific logic.

## Antigravity workflow

Use [BUILDING_WITH_ANTIGRAVITY.md](BUILDING_WITH_ANTIGRAVITY.md) as the build contract. Implement in the order in `TASKS.md`, keep the documentation aligned with code, and preserve the no-login demo path while adding future live connectors.

## Changes to employee behavior

When changing an employee role:

1. Update [AGENTS.md](AGENTS.md).
2. Update the relevant SOP or prompt.
3. Add an example task and handoff.
4. Add an evaluation case in [EVALUATION.md](EVALUATION.md).
5. Confirm that the change does not bypass permission or approval rules.

## Changes to the graph schema

When adding a node or relationship:

1. Update [DATA_MODEL.md](DATA_MODEL.md).
2. Define stable identifiers and source fields.
3. Add an idempotent write path.
4. Add a read query used by at least one employee.
5. Add a migration or compatibility note.

## Attribution

If code or prompts are adapted from third-party repositories, preserve their license and attribution files and document the source in the project README.
