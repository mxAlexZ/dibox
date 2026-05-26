---
name: update-adr
description: "Use when: creating, auditing or updating ADRs in docs/adrs/ from discussion, user feedback, or implementation changes; syncing ADRs with source code; splitting ADRs to park deferred ideas and expand active decision threads."
---

# Update ADR

## Goal
Keep ADRs decision-useful and accurate as context and code evolve.
Turn discussion context, implementation changes, and lifecycle splits into concise ADR updates that preserve non-obvious rationale, constraints, and decision context while aligning with current source code.

## Rules
- Prioritize high-value context that is expensive or impossible to infer from code: rationale, trade-offs, non-obvious constraints, known pitfalls.
- Exclude low-value detail that is easy to recover from source code.
- Focus on 'why': decisions, DX trade-offs, and open questions. Include implementation detail only when it changes architecture or decision logic.
- Instead of code-specific names like methods or arguments, use descriptive terms for concepts and roles; only essential key class names related to the specific topic can be included (like `DependencyGraph` in "Dependency Graphs" document).
- ADRs are not timelines: remove stale context by default. Keep historical notes only when they still affect future decisions.
- Keep status accurate and explicit: status signals decision maturity to readers. Use values like proposed, partially implemented, implemented.
- Prefer incremental updates over rewrites; preserve decision history only when it still carries decision value.
- Use file-path cross-links to related ADRs instead of duplicating context.
- Each link should be supported by a one-line description why the linked ADR is relevant to the current one. Avoid vague "see also" links with no retrieval cues.
- After writing or updating an ADR, update its one-line description in `docs/adrs/index.md` with retrieval cues: area, main problem/decision focus, key terms. Avoid vague summaries with no searchable anchors.

## Style
- Prose must be dense.
- Use headers for logical sections
- Avoid diagrams and tables — use bullets or prose instead.
- No bold/italic emphasis or decorative formatting.

## Workflow
1. Identify affected ADRs: scan `docs/adrs/index.md` and read relevant files.
2. Determine the update type and act accordingly:
   - New ADR from discussion or feedback: frame the problem, outline candidate solutions, then record the chosen path, its trade-offs, and the 'why'.
   - Post-implementation sync: verify existing claims against source code. Remove or correct stale details; don't rewrite the whole ADR — only what drifted.
   - Parking and splitting: when an ADR accumulates multiple branches, split it into focused documents.
3. Apply changes minimally — incremental edits, not rewrites.
4. Add or update cross-links to related ADRs when decision boundaries overlap.
5. Update the ADR status or its sections to reflect its current maturity and implementation state.
6. Run a quick quality check to see if the rules are followed.
7. Update the one-line description in `docs/adrs/index.md` — term-dense, include key names, concepts, main problem focus.
