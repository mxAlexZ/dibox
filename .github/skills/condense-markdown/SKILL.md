---
name: condense-markdown
description: "Use when: condense/format Markdown or ADRs (e.g., 'condense this adr', 'format this adr'); reduce tokens without losing meaning; remove decorative formatting."
---

# Condense Markdown

## Goal

Reduce token count while preserving meaning and all constraints.

## Rules

- Preserve technical meaning: file paths, URLs, exact terms, and “must/never” constraints
- Preserve Markdown that carries meaning: headings, lists, links, code fences, and inline code
- Remove decorative emphasis: bold/italic formatting → plain text
- Convert tables → bullets (each row becomes one bullet; include column names as inline labels)
- Remove filler and repetition; drop preambles that restate the header
- Merge adjacent bullets only when they truly restate the same point
- Keep nesting depth ≤ 2; prefer inline qualifiers over deep sub-bullets
- Don’t silently drop unique facts, constraints, edge cases, or exceptions
- If unsure whether something is redundant, keep it
- Fix obvious broken paths/references discovered during editing

## Workflow

1. Read the full file to understand intent.
2. Normalize structure (strip bold/italic; tables → lists).
3. Tighten prose (direct phrasing, remove filler, merge true duplicates).
4. Final pass: verify no constraints/facts were lost; verify links/paths.
5. Report a short summary: what changed, any confusing/ambiguous points found, and measurable deltas (word/character counts if available; token reduction/% only if the environment provides it).
