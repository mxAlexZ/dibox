---
name: update-adr
description: "Use when: creating, auditing or updating ADRs in docs/adrs/ from discussion, user feedback, or implementation changes; syncing ADRs with source code; splitting ADRs to park deferred ideas and expand active decision threads."
---

# Update ADR

## Goal
Keep ADRs decision-useful and accurate as context and code evolve.
Turn discussion, implementation changes, and lifecycle splits into concise updates that preserve non-obvious rationale, trade-offs, constraints, and pitfalls while staying aligned with current source code.

## Mental model — read before editing
Four ideas drive every rule below. If an edit violates one, it is wrong even if it "reads fine."

1. Self-sufficient present. An ADR describes the design as it stands now, as if written today from scratch. A reader with no memory of past versions must understand it fully. Never reference the document's own history ("the original draft", "previously", "we changed", "this used to").
2. Tense matches status. The words must match what the code actually does. An implemented feature is described in plain present tense ("DIBox governs X"). A proposal is described as future ("DIBox would govern X"). Mixing them is the most common defect.
3. Not a changelog. Capture the current decision and its rationale, not the sequence of decisions that led here. Keep a historical note only when it still changes a future decision (e.g. "approach X was rejected because Y" that prevents re-litigating it).
4. Code is the source of truth. Before asserting how something behaves, confirm it in the source. Never restate a claim already in the doc without checking it still holds.

## Rules

### Content
- Prioritize context that is expensive or impossible to recover from code: rationale, trade-offs, non-obvious constraints, known pitfalls, rejected alternatives.
- Exclude detail that is trivially readable from source. Include implementation detail only when it changes architecture or decision logic.
- Use descriptive terms for concepts and roles, not code-specific method or argument names. Include only essential key type names tied to the topic (e.g. `DependencyGraph` in the dependency-graph ADR).

### Framing and tense (the recurring defect — check every sentence)
- Describe the current design directly. Do not frame it as a change from a past state.
- Match tense to status. In an implemented ADR, every claim about behavior is present-tense fact.
- Scan for these watch-words; each usually signals a defect in an implemented doc:
  - "should", "will", "would", "is going to" → proposal language leaking into shipped behavior. Use present tense: "should report" → "reports".
  - "now", "no longer", "currently", "still" → implies a before/after the reader cannot see. State the present fact without the comparison.
  - "the original/previous/old draft", "we changed", "used to", "replaced X with" → the doc is narrating its own history. Delete the narration; state what is.
  - "Replace X with Y" / "Add Y" as a section's main verb (for work already done) → describe Y as the current design, not as an action to perform.
- Examples (from real fixes):
  - Bad: "Replace the hard-coded guard with an implicit creation policy." Good: "DIBox governs implicit creation with an explicit policy rather than a fixed guard."
  - Bad: "The API should cover package ownership." Good: "The API covers package ownership."
  - Bad: "The original draft framed scanning as the answer to boilerplate." Good: "Strict mode requires every managed type to be explicitly registered."
- Exception: genuinely future or proposed work stays in future tense, and a rejected-alternative note stays as a note — but label it as such, and keep it only if it still guides a decision.

### Status
- State status explicitly at the top: proposed, partially implemented, or implemented.
- Judge status by the core feature, not by every wish-list item. Ask: does the missing piece make the described feature incomplete or unusable? If yes, it is "partially implemented". If the missing piece is a separate, independently shippable enhancement, the feature is "implemented" and the enhancement is noted elsewhere (a trade-off or a dedicated "possible extension" section), not in the status line.
- Do not over-qualify. Minor polish or YAGNI follow-ups do not belong in the status line and do not downgrade status.
- When syncing after implementation, re-read the status line last and confirm it matches the body.

### Links and index
- Cross-link related ADRs by file path instead of duplicating their context.
- Give each link a one-line reason it is relevant, with retrieval cues. No bare "see also" links.
- After any ADR change, update its one-line entry in `docs/adrs/index.md`: area, main problem/decision focus, key terms. Avoid vague summaries with no searchable anchors.

### Style
- Dense prose. Headers for logical sections. Bullets or prose, no tables or diagrams. No bold/italic or decorative formatting.

## Workflow
1. Locate: scan `docs/adrs/index.md`, read the target ADR and closely related ones.
2. Verify: for a post-implementation sync, confirm each existing claim against source before trusting it. Note what drifted.
3. Choose the update type:
   - New ADR: frame the problem, outline candidate solutions, record the chosen path with its trade-offs and the 'why'.
   - Sync: correct or remove only what drifted; do not rewrite untouched sections.
   - Split: when an ADR holds several branches, move deferred ones into focused documents.
4. Edit minimally and in the correct tense for the status.
5. Update or add cross-links where decision boundaries overlap.
6. Reconcile the status line with the body.
7. Update the `docs/adrs/index.md` entry.
8. Run the self-review checklist below.

## Self-review checklist — run before finishing
Answer each; fix any "no" before handing back.
- Self-sufficient: would this read correctly to someone who never saw a prior version? No references to the doc's own history?
- Tense matches status: no "should/will/now/no longer/used to/replace" leaking into an implemented doc's behavior claims?
- Verified: is every behavior claim confirmed against current source, not assumed?
- Status honest: does the status line reflect the core feature, without over-qualifying on optional follow-ups?
- Links: does each cross-link carry a concrete reason and retrieval cue?
- Index synced: does the `index.md` entry match the updated content?
- Minimal: were untouched, still-correct sections left alone?
