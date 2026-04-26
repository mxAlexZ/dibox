# ADRs in DIBox: Why This Ecosystem Exists

This document explains why ADRs matter in DIBox, what knowledge they preserve, and how that knowledge evolves with the codebase.

## Why ADRs exist in DIBox

Source code describes behavior, but it cannot reliably preserve decision intent. It rarely captures why one trade-off was accepted, which alternatives were rejected, or which constraints were considered non-negotiable at the time.

Without that context layer, teams repeatedly pay the same design cost: debates are re-opened, old constraints are rediscovered late, and implementations optimize local simplicity while drifting from product-level developer experience goals. ADRs preserve the reasoning so that future implementation and documentation work remains aligned with the same principles.

## Information economics of ADRs

ADRs are most valuable when they store high-cost knowledge: rationale, trade-offs, non-obvious constraints, known pitfalls, and rejected alternatives.

They are least valuable when they duplicate low-cost knowledge that can be read directly from source code. In that sense, ADR quality is not about volume. It is about preserving context that lowers future decision cost.

## Why this ecosystem improves delivery

The ADR ecosystem creates leverage in four areas:

- Implementation quality: explicit rationale and constraints reduce decision latency and architecture regressions.
- Documentation quality: ADRs provide the motivation layer that keeps public docs consistent with design intent.
- Context efficiency: indexed, focused ADRs enable targeted retrieval for humans and AI, reducing context overflow.
- Team continuity: design reasoning survives contributor turnover, so teams inherit intent, not just current code shape.

Operational retrieval and update workflow is defined in repository instructions and the `update-adr` skill.

## ADR lifecycle

ADRs in this repository are expected to move through the following lifecycle.

This lifecycle is a knowledge-refinement loop: broad idea exploration is gradually compressed into stable decision context.

### 1. Exploration

Early-stage brainstorming and option discovery.

Typical signals:
- multiple alternatives and thought experiments,
- broad trade-off analysis,
- open questions with no final direction yet.

### 2. Transition

Implementation has started or parts are already implemented.

Typical signals:
- mixed content: current behavior + proposed direction,
- constraints discovered from real implementation,
- narrowed option space and clearer recommendations.

### 3. Context record

Feature behavior is mostly established and ADR becomes a stable high-level rationale document.

Typical signals:
- motivations and trade-offs are primary,
- implementation detail is intentionally thin,
- ADR supports user docs and future implementation changes.

### 4. Parking and splitting

As an ADR matures, its idea branches naturally diverge. Some threads gain enough depth and ongoing relevance to become their own document; others settle into deferred context — still valuable as background, but no longer driving active decisions. When this divergence becomes visible, the ADR splits into focused documents aligned with each branch.

### 5. Source-sync maintenance

As code evolves, ADRs are periodically synchronized.

This is not a rewrite cycle. The goal is to keep architectural intent accurate while minimizing wording churn.

## Why maintenance matters

ADR maintenance is a trust mechanism, not clerical work. Without it, three failure modes accumulate.

The first is ambiguity about maturity. Without explicit status, readers cannot tell whether a document is an early brainstorm or settled context, and treat exploration as policy or dismiss decisions as unresolved. Marking status resolves this.

The second is drift. As code evolves, outdated claims linger uncorrected and the ADR layer gradually diverges from implementation reality. Keeping claims source-verifiable prevents this, so the context layer stays auditable rather than becoming narrative fiction.

The third is retrieval failure. ADR value is only realized if the right document can be found under time pressure. Dense, searchable index descriptions make targeted retrieval possible for both humans and AI working under context-window constraints.

Together these practices keep ADRs decision-useful rather than turning them into static historical artifacts.
