---
name: update-adr
description: "Use when: creating, auditing, updating, condensing, or restructuring ADRs in docs/adrs/ from discussion, user feedback, or implementation changes; syncing ADRs with source code; splitting ADRs to park deferred ideas. Examples: 'dense up this ADR', 'format this adr', 'split this ADR'."
---

# Update ADR

## Goal
Keep ADRs decision-useful and accurate as context and code evolve.
Turn discussion, implementation changes, and lifecycle splits into concise updates that preserve non-obvious rationale, trade-offs, constraints, and pitfalls while staying aligned with current source code.
Pursue the document's purpose: a reader with a decision in hand must leave able to answer what problem, what was decided, what constrains it, and what is still open. Size is not the scoreboard.

## Mental model — read before editing
Six ideas drive every rule below. If an edit violates one, it is wrong even if it "reads fine."

1. Self-sufficient present. An ADR describes the design as it stands now, as if written today from scratch. A reader with no memory of past versions must understand it fully. Never reference the document's own history ("the original draft", "previously", "we changed", "this used to").
2. Tense matches status. The words must match what the code actually does. An implemented feature is described in plain present tense ("DIBox governs X"). A proposal is described as future ("DIBox would govern X"). Mixing them is the most common defect.
3. Not a changelog. Capture the current decision and its rationale, not the sequence of decisions that led here. Keep a historical note only when it still changes a future decision (e.g. "approach X was rejected because Y" that prevents re-litigating it).
4. Code is the source of truth. Before asserting how something behaves, confirm it in the source. Never restate a claim already in the doc without checking it still holds.
5. Every section answers a reader question. A section whose question you cannot name in one line is an artifact of the discussion that produced it, not decision context.
6. Every named concept is a tax. A term earns its place only if it names something a user encounters or a constraint the design turns on.

## Purpose audit — before any edit
1. Read the whole document (and closely related ADRs), then restate from memory what it establishes: the problem, the decision, the constraints forcing it, what is still open. Write the restatement without quoting. If you find yourself copying sentences, you have not understood it.
2. Write a section ledger — one line per existing section: the question it answers for the reader, and a verdict (keep / tighten / merge into X / cut / restructure). For a new ADR, the ledger is the planned skeleton: every proposed section must have a question.
3. A section whose question you cannot name in one line is an artifact. The verdict is cut or merge, never tighten. "Tighten" is only for a section that already answers a real question, verbosely.
4. Rewrite from the restatement; pull exact constraints, type names, and "must/never" wording back from the original. Restore a fact only if it constrains a decision, not merely because it is true.

Scope: full ledger for a condense, restructure, split, or new ADR. For a code-sync, ledger only the sections the drift touches.

Show the restatement and the ledger before editing when the update type is condense, restructure, split, or new. For a code-sync, keep the ledger internal unless a stop-and-wait trigger fires.

## Stop and wait
Do not edit yet if any of these is true. Present the restatement, the ledger, and the proposed irreversible change; wait for approval.

- Cutting rationale, a trade-off, or a rejected alternative that is recorded nowhere else.
- Resolving or closing a listed open question. Propose the resolution; do not silently keep it open and do not silently close it.
- Removing or renaming a term other ADRs use.
- Changing the document's section skeleton (merge / cut / restructure / new headings).

Proceed unasked on: prose tightening, dropping what a linked ADR already covers, deleting a code sample that illustrates nothing, tense and status fixes, index one-liners.

## Rules

### Content
- Prioritize context that is expensive or impossible to recover from code: rationale, trade-offs, non-obvious constraints, known pitfalls, rejected alternatives.
- Exclude detail that is trivially readable from source. Include implementation detail only when it changes architecture or decision logic.
- Use descriptive terms for concepts and roles, not code-specific method or argument names. Include only essential key type names tied to the topic (e.g. `DependencyGraph` in the dependency-graph ADR).
- Remove content that no longer serves a reader question, even when true, unique, and stated nowhere else. Truth is not a reason to keep a discarded intermediate step.

### Vocabulary
- A term earns its place only if it names something a user encounters or a constraint the design turns on.
- If you cannot point to where it is defined in this document and why the design needs it, it came from a discussion, not the design. Drop it; describe the behavior in ordinary language.
- Placeholder names in a sketch stay labeled as placeholders. They must not become the document's local vocabulary.

### Section shape
- Problem first, briefly, then the answer. One example per problem.
- No "not this, not that, it is this" framing. Contrast a named alternative at most once, and only when that contrast is the decision.
- Code samples must show what prose cannot state as briefly. An ADR is not a user guide. If you cannot say what the sample illustrates in one line, delete it.
- Do not explain a neighbouring ADR's concept; the link is the explanation.
- Unlocked candidates are open questions, not a section. A section exists only when there is a decision, or a problem that forces one.

### Open questions
- Each item traces to a question the body raises. An item with no home in the body is a leftover; drop it or write the missing problem first.
- If the answer is already clear, it is not open: state it in the body.
- Something outside DIBox's responsibility is not an open question. Either a one-line boundary in the body, or omit it.
- Separation is not rejection. A parked mechanism stays parked, with a link, not a "rejected" label.

### Framing and tense (the recurring defect — check every sentence)
- Describe the current design directly. Do not frame it as a change from a past state.
- Match tense to status. In an implemented ADR, every claim about behavior is present-tense fact.
- Scan for these watch-words; each usually signals a defect in an implemented doc:
  - "should", "will", "would", "is going to" → proposal language leaking into shipped behavior. Use present tense: "should report" → "reports".
  - "now", "no longer", "currently", "still" → implies a before/after the reader cannot see. State the present fact without the comparison.
  - "the original/previous/old draft", "we changed", "used to", "replaced X with" → the doc is narrating its own history. Delete the narration; state what is.
  - "Replace X with Y" / "Add Y" as a section's main verb (for work already done) → describe Y as the current design, not as an action to perform.
- Examples (from real fixes):
  - Bad: "Replace the hard-coded guard with a missing-binding policy." Good: "DIBox governs missing bindings with one policy rather than overlapping controls."
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
- A link whose only job is to say the target is a different problem is not relevant. Drop it.
- After any ADR change, update its one-line entry in `docs/adrs/index.md`: area, main problem/decision focus, key terms. Avoid vague summaries with no searchable anchors.

### Style
- Dense prose. Headers for logical sections. Bullets or prose, no tables or diagrams. No bold/italic or decorative formatting.
- Nesting depth at most two; prefer inline qualifiers over deep sub-bullets.

### Working with feedback
- Treat a flagged defect as a class. Sweep the whole document, plus any sibling ADRs edited in the same session, for the same pattern. Repeating a named defect is the most expensive failure mode.
- When the user proposes a cut, evaluate it. Argue back if it is load-bearing; agree and cut if it is not. "Agreed" without the evaluation is a miss.

## Workflow
1. Locate: scan `docs/adrs/index.md`, read the target ADR and closely related ones.
2. Verify: for a post-implementation sync, confirm each existing claim against source before trusting it. Note what drifted.
3. Purpose audit (restatement + ledger) as above. Stop and wait if a trigger fires.
4. Choose the update type:
   - New ADR: frame the problem, outline candidate solutions, record the chosen path with its trade-offs and the 'why'. Every section in the ledger has a reader question.
   - Sync: correct or remove only what drifted in the sections the ledger covers; do not rewrite untouched sections that still answer their question.
   - Split: when an ADR holds several branches, move deferred ones into focused documents. Separation is not rejection.
   - Condense / restructure: rewrite from the restatement; pull constraints back; cut artifacts.
5. Edit in the correct tense for the status.
6. Update or add cross-links where decision boundaries overlap.
7. Reconcile the status line with the body.
8. Update the `docs/adrs/index.md` entry.
9. Run the self-review checklist below.

## Self-review checklist — run before finishing
Answer each; fix any "no" before handing back.
- Purpose: can a first-time reader answer the problem, the decision, the constraints, and what is open? Does every remaining section earn its place with a nameable question?
- Vocabulary: is every named concept defined here and required by the design?
- Self-sufficient: would this read correctly to someone who never saw a prior version? No references to the doc's own history?
- Tense matches status: no "should/will/now/no longer/used to/replace" leaking into an implemented doc's behavior claims?
- Verified: is every behavior claim confirmed against current source, not assumed?
- Status honest: does the status line reflect the core feature, without over-qualifying on optional follow-ups?
- Open questions: does each item trace to the body? Nothing already decided, nothing outside DIBox's job?
- Links: does each cross-link carry a concrete reason and retrieval cue, without re-explaining the target?
- Index synced: does the `index.md` entry match the updated content?
- Minimal wording: were still-correct sections that still answer a reader question left alone in wording? Artifacts were cut even if true and unique?

## Report
What a first-time reader can now answer. Each removal, with one of: covered by a linked ADR / no question served / settled and folded into the decision / outside scope. Never word counts or token percentages.
