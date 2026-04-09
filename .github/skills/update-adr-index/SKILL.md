---
name: update-adr-index
description: "Use when: updating docs/adrs/index.md; syncing Index entries with docs/adrs files; adding/removing missing ADR links; refreshing short searchable ADR descriptions in full-rescan or targeted mode."
---

# Update ADR Index

## Goal

Keep docs/adrs/index.md accurate and searchable by maintaining the Index section with concise, high-signal descriptions.

## Rules

- Constraints:
  - Only update the Index section in docs/adrs/index.md.
  - Do not change text outside the Index section.
  - Keep edits minimal; avoid unnecessary wording churn.
  - If a description is already good enough, keep it as-is unless there is an obvious mistake.
- Modes:
  - Full rescan: read all ADR files and refresh every description. Use when architecture changed broadly, many ADRs were touched, or quality is unknown.
  - Targeted update (default): update only requested/touched/missing files and affected links. Use for routine maintenance after one or a few ADR edits.
  - Sync-only: add/remove Index links from filesystem comparison. Keep existing descriptions unless they are clearly wrong.
- File sync:
  - List files under docs/adrs and compare against Index links.
  - Exclude docs/adrs/index.md itself.
  - Add entries for files present on disk but missing in Index.
  - Remove entries for links whose files no longer exist.
  - Preserve established Index ordering when possible; avoid reordering unrelated entries.
- Description quality:
  - Keep each description to one line.
  - Include key API names, terms, or failure modes from the document.
  - State the core problem or decision, not generic wording.
  - Leave unchanged if it already meets this bar.
- Prefer high-signal terms when relevant: implicit self-binding, strict flag, zero-dependency guard, contextvar, add_bindings.

## Workflow

1. Select mode: full rescan, targeted update, or sync-only.
2. Read docs/adrs/index.md and parse the Index section.
3. List docs/adrs files and compute missing/stale entries.
4. Read only files needed for the chosen mode.
5. Update Index bullets with minimal changes.
6. Final checks:
   - only Index section changed,
   - file list matches docs/adrs,
   - unchanged-good descriptions were preserved.

## Output Summary

Report:
- mode used,
- entries added/removed,
- descriptions changed and why,
- whether no-op was possible.
