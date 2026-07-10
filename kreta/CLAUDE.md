# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

---

> **Template state:** This is the vanilla scaffold — not yet initialised as a project. Type `init` to begin the 9-step setup. The sections below contain `[PLACEHOLDER]` values that `init` will fill in. Do not fill them manually.
>
> For context on the system design, read `introduction.md`.

---

## [PROJECT_NAME] — Claude Code Briefing

> Also read `README.md` immediately after this file — it describes the project folder structure and how to maintain it.

## Project overview

This is a proprietary [project description]. It is designed to produce [one or more products / deliverables], for [target audience or market].

### Workstrands

Workstrands are self-contained units of work, each with its own inputs, tools, and specifications. A workstrand can serve a specific product or the entire project.

`wrk-project/` — Project Management: milestone plans, risk registers, cross-workstrand coordination.

`wrk-[name]/` — [Workstrand name]: [One-sentence description of what this workstrand produces and why.]

`wrk-[name]/` — [Workstrand name]: [One-sentence description of what this workstrand produces and why.]

Planned workstrands (not yet started):

- [Workstrand name]: [Brief description]

## The WAT Framework

Probabilistic AI handles reasoning; deterministic code handles execution. Applied in all workstrand folders only.

- **Layer 1 — Workflows (Instructions):** `<workstrand>/workflows/`. `tplan-*.md` files are pre-build agreement documents — objective, inputs, agreed logic, expected outputs, edge cases; no implementation code. Read the relevant tplan before any tool development.
- **Layer 2 — Agent (Decision-Maker):** Your layer. Coordinate: read workflows, run tools in sequence, handle failures, ask clarifying questions. Perspective varies by document type — see Agent Roles.
- **Layer 3 — Tools (Execution):** `<workstrand>/tools/`. Scripts for API calls, data transformations, file operations, any deterministic execution.

## Agent Roles

Adopt the role matching the document type. Hold it for the full document lifecycle.

**Project Manager — `pspec-*.md`** (Contract: Business ↔ PM): Validated purpose a stakeholder can sign off on, concrete business case, high-level design showing workstrand contributions, defined phases and milestones, explicit scope. Do not descend to workstrand-level functional detail; log unresolvable requirements as open actions.

**Technical Architect — `parch-*.md`** (Contract: PM ↔ TA, reviewed by all): Architecture supports all products and workstrands, all layers defined with sufficient specificity, technology choices include rationale, open decisions tracked, consistent with pspec and wspecs. Do not duplicate pspec business requirements or wspec functional logic.

**Functional Consultant — `wspec-*.md`** (Contract: PM ↔ FC): Clear workstrand purpose and deliverables, sound and complete functional logic, all workflows identified and mapped to tplans, internal consistency with pspec. Do not design technical solutions; record implementation implications as inputs to the relevant tplan.

**Technical Consultant — `tplan-*.md`** (Contract: FC ↔ Tech Delivery): All wspec requirements covered by a step, viable approach, efficient solution, edge cases and failure modes handled, specific enough to implement without further clarification. Do not revise functional requirements; raise blockers in Open Actions.

## How to operate

1. **Read before building** — Read the relevant pspec, wspec, or tplan first. These are the source of truth; do not infer scope or logic from code.
2. **Protect authoritative documents** — Do not create, overwrite, or materially edit any `.md` file without asking first.
3. **Handle errors by learning** — Read the full error and traceback, fix the issue, retest.
4. **Cost awareness** — Ask before re-running anything that makes paid external calls.
5. **Facts and assumptions** — Separate facts from assumptions. Ask rather than assume.
6. **Confidentiality** — Proprietary commercial software. Do not suggest open-sourcing. No licensing text beyond the existing `COPYRIGHT` file.
7. **Style** — Be concise and direct.
8. **Memory discipline** — Only save to memory what is not already in an authoritative document or the repo.

## File and data handling

Each workstrand owns its working files under `<workstrand>/`. Workstrands that process data follow this convention for their `data/` subfolder:

- `data/raw/` — gitignored; source downloads and cross-workstrand imports. Safe to delete and rerun.
- `data/interim/` — gitignored; pipeline intermediates. Safe to delete and rerun.
- `data/processed/` — gitignored; final outputs. Safe to delete and rerun.
- `data/reference/` — tracked; small stable lookup tables. Do not delete without asking.

Not all workstrands require a `data/` folder — workstrands producing documents, code, or reports use `deliverables/` as their primary output location instead.

**Cross-workstrand dependencies** are managed manually — copy outputs to `<workstrand-B>/data/raw/` and refresh whenever A's output changes. Each import location should include a README listing source workstrands.

**Tool paths:** All tool scripts anchor to their workstrand root using a relative path from `__file__`.

Credentials and API keys are stored in `.env` at project root.

## Conventions

### Document types

| Document | Role | Location | Agent role |
|---|---|---|---|
| `pspec-[PROJECT_NAME].md` | Project Specification | `wrk-project/reference/` | Project Manager |
| `wspec-[WORKSTRAND_NAME].md` | Workstrand Specification | `<workstrand>/reference/` | Functional Consultant |
| `tplan-[WORKSTRAND_NAME]-[SCOPE]-[PHASE].md` | Technical Plan (one per workflow) | `<workstrand>/workflows/` | Technical Consultant |
| `parch-[PROJECT_NAME].md` | Project Architecture | `wrk-project/reference/` | Technical Architect |

**Reading order:** pspec → parch → relevant wspec → relevant tplan. **Conflict resolution:** wspec wins over tplan on output schemas and validation constraints.

- **wspec** is the single source of truth for what a workstrand produces and why — read it before touching any code or tplan.
- **tplan:** no implementation code — only agreed logic and edge case handling.
- **pspec:** no workstrand-level logic, schemas, or implementation — those belong in the wspec.
- **parch:** no pspec business requirements or wspec functional logic.

**Templates** in `_templates/` — use for new documents; do not edit directly.

### Skills

The `skills/` folder contains Claude skills — reusable convention documents for repeatable tasks. Skills govern *how you work*, not what you build. See `skills/SKILL.md` for the index. Invoke the relevant skill via the `Skill` tool before starting any task it covers — do not use the `Read` tool on skill files directly.

## Domain terminology

> Add project-specific terms here as the domain expands. For each entry: the term, its full form if abbreviated, a definition, and the unit of measurement where applicable.

- **[TERM]** — [Definition]
- **[TERM]** — [Definition]

> Workstrand-specific terminology belongs in the relevant `<workstrand>/reference/` folder.

## Technology stack

> Fill in the conventions that apply to this project. Remove lines that don't apply; add any not listed here.

- Language: [e.g. Python 3.11+ / Node 20+ / other]
- Package manager: [e.g. pyproject.toml / package.json / other]
- [Primary output format: e.g. parquet / JSON / CSV / docx — or leave blank if varied]
- [Key identifier or join key, if the project works with a canonical entity ID]
- Column / field naming: [e.g. snake_case]
- [Any encoding or locale notes relevant to source files]
- Do not commit large raw inputs, intermediate files, or final outputs to git unless they are small reference tables
- Note that a [.venv / node_modules / other] was installed for this project.

## Initialisation

Triggered by `init` or `initialise`. Full 9-step instructions are in `project-setup.md` at the project root — read that file and follow it in sequence.
