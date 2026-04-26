## Project
DIBox is an async-native Python dependency injection library, early development stage. Auto-wires classes via type hints to eliminate boilerplate. Mission: simplicity and developer experience.
Design principle: Progressive Disclosure of Complexity — zero-config defaults for common cases, explicit APIs for advanced ones.

## Key notes
- API is unstable; improvements and new features are welcome.
- Prefer best solutions over quick hacks. When there are multiple options, summarize and let the user choose.
- Prioritize simplicity and DIBox idioms. Full production-use-case coverage is the goal — not reduced scope. Flag designs that trade simplicity for power without clear justification.

## Code style
- Python 3.11+, strictly typed with pyright. Annotate all functions; omit return type for `None` or obvious cases.
- Before changes touching more than one function/class, or with multiple reasonable approaches: present a plan and wait for approval.
- Docstrings: Google style, concise, non-obvious. Skip for self-explanatory functions.
- Clarity over hyperbole. Engineering jokes welcome when relevant.
- Markdown: concise, minimal formatting (no excessive bolding/tables), readable without rendering.

## Tools
- Tests: `uv run pytest`
- Type checking: `uv run pyright`

## Context Workflow
For non-trivial tasks — feature work, design changes, questions, or anything touching behavior, trade-offs, or architecture — consult ADRs first. Skip for purely mechanical edits (imports, renaming, formatting).
- Start from `docs/adrs/index.md`; Use index summaries to read 2-4 most relevant ADRs; expand reads only if open questions remain.
- Treat source code as implementation truth; treat ADRs as rationale and design intent.
- If ADR and code diverge, call it out and propose minimal updates.
- When writing or updating ADRs, use the `update-adr` skill.

## Documentation
- `README.md`: public-facing intro and usage examples.
- `docs/adrs/`: ADR design context database — decisions, trade-offs, and open questions.
- `docs/adrs/index.md`: ADR entrypoint and content map for targeted retrieval.
