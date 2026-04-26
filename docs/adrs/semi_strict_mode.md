# Semi-Strict Resolution

Status: Proposed

This document proposes a third resolution strategy between permissive implicit self-binding
and fully explicit strict mode.

Related ADRs:

- [Resolution Modes](./resolution_modes.md): defines current `strict`/permissive behavior and the proposed zero-dependency guard this mode depends on.
- [bind(...) API](./bind_api.md): defines explicit-binding precedence and matcher behavior that semi-strict must preserve.
- [Entrypoints](./entrypoints.md): defines how `provide()` and imperative entrypoint patterns interact with resolution policy.
- [Diagnostics and Introspection](./diagnostics.md): defines error-locality and graph introspection expectations.
- [Package-aware auto-binding](./package_binding.md): relevant for optional package ownership boundaries on transitive expansion.

## 1. Problem

In `strict=True`, every transitive concrete dependency must be explicitly registered.
`bind_many()` reduces repetition only for the listed types, but it does not remove the need to
bind intermediate classes. Binding noise grows with graph depth even for conventional concrete services,
and imperative entrypoint patterns like `call()`/`partial()` remain verbose when only root-level intent is interesting.
The goal is a mode that preserves strict-style guardrails at graph boundaries while eliminating
registration churn for intermediate concrete dependencies.

## 2. Proposal: Semi-Strict (Seeded) Resolution

Add a third mode (name TBD: `semi_strict`, `seeded`, or `anchored`) with this rule:

-   Only explicitly bound types are valid resolution roots.
-   While resolving those roots, missing transitive dependencies may be implicitly self-bound,
    but only if they pass autowire guards.

This is explicit-roots + implicit transitive closure.

### 2.1. Required guards

Semi-strict should not reuse permissive behavior unmodified. It should require:

-   Concrete-type check (same as today).
-   Zero-dependency guard (see [Resolution Modes](./resolution_modes.md#3-proposed-zero-dependency-guard-for-permissive-mode)).
-   Existing explicit binding precedence rules from [bind(...) API](./bind_api.md).

Because the zero-dependency guard is still proposed, semi-strict depends on adopting that guard
or an equivalent safety filter before rollout.

### 2.2. Current implementation constraints

-   Current container API is a boolean `strict` flag on `DIBox(...)`; introducing a third mode
    needs either an enum-like mode API or a compatibility mapping strategy.
-   In source, `strict=True` currently gates implicit self-binding fallback for unbound concrete
    types; semi-strict should be specified as a narrow extension of that fallback logic.
-   `provide()` is implemented today, while imperative entrypoint behavior is still evolving;
    mode semantics should be specified first for `provide()` and then extended consistently.

### 2.3. Non-goals

-   Not a replacement for `strict=True`.
-   No inference of abstract/interface mappings; explicit `bind()` remains required.
-   No change to module precedence rules.

## 3. Trade-offs

### 3.1. Benefits

-   Major boilerplate reduction compared with strict mode in deeper dependency graphs.
-   Stronger fit for imperative entrypoint patterns from [Entrypoints](./entrypoints.md): entrypoint roots stay explicit without binding every intermediate class.
-   More bounded and analyzable than permissive mode because expansion starts from explicit seeds.

### 3.2. Risks

-   Weaker testing guard than strict mode: missing intermediate mocks may silently instantiate real concrete classes.
-   Lower configuration explicitness: constructor changes can alter runtime graph behavior without binding diff changes.
-   Potential error-locality regressions without diagnostics (failures move toward low-level leaf types).
-   Semantics get harder around dynamic matching patterns (predicate bindings, unions, [named bindings](./named_bindings.md)), so behavior must be documented precisely.

### 3.3. Mitigations

-   Keep `strict=True` semantics unchanged.
-   Make zero-dependency guard mandatory for semi-strict.
-   Extend diagnostics to mark auto-expanded nodes and preserve root-to-leaf failure paths (see [Diagnostics and Introspection](./diagnostics.md)).
-   Keep this as an explicit mode, not a hidden behavior change of strict mode.

## 4. Open Questions

-   API shape: extend boolean `strict` vs switch to enum-like resolution mode.
-   Introspection model: whether auto-expanded transitive nodes are persisted as explicit bindings or represented as derived graph nodes.
-   Boundary policy: whether package/module ownership constraints should limit transitive auto-expansion (related to [Package-aware auto-binding](./package_binding.md)).
-   Future per-call overrides: whether to allow mode override for `provide()` / `call()` and how to keep diagnostics understandable.