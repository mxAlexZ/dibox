# Semi-Strict Resolution

Status: Implemented. Core semi-strict resolution and implicit creation policy integration are implemented; diagnostics/introspection refinements remain follow-up improvements.

This document defines a third resolution strategy between permissive implicit self-binding
and fully explicit strict mode.

Related ADRs:

- [Strict Mode](./strict_mode.md): defines the explicit-binding baseline that semi-strict keeps at the root boundary.
- [Implicit Self-Binding](./implicit_self_binding.md): defines the permissive transitive expansion behavior semi-strict reuses below explicit roots.
- [Implicit Creation Policy](./implicit_creation_policy.md): filters eligible unbound concrete types during transitive expansion.
- [Entrypoints](./entrypoints.md): defines how `provide()` and imperative entrypoint patterns interact with resolution policy.
- [Diagnostics and Introspection](./diagnostics.md): defines error-locality and graph introspection expectations.

## 1. Motivation

Strict mode conflates two distinct concerns: declaring which types are owned resolution roots (intent) and registering every transitive implementation detail (structural noise). Most intermediate concrete services have nothing to configure — their dependencies follow directly from their constructor signature, and there is nothing to decide about them. Requiring an explicit `bind()` for each adds registration churn that scales with graph depth without adding any intent.

Permissive mode removes that churn but also removes control: any unbound concrete type may be resolved, blurring container ownership and making test isolation unreliable.

Semi-strict addresses this gap. The developer declares which types are owned resolution roots; the container fills in concrete transitive dependencies automatically. Ownership stays explicit at the boundary — where it matters — without forcing every interior class to be pre-registered. This is also the natural fit for imperative entrypoints like `call()` and `partial()`, where the goal is to express a set of root services and have the container wire them without a full explicit graph declaration.

## 2. Decision and Contract

Semi-strict mode uses explicit roots with implicit transitive expansion:

-   Only explicitly bound types are valid resolution roots.
-   While resolving from those roots, missing transitive concrete dependencies may be implicitly self-bound when the implicit creation policy permits them.

Resolution mode determines where implicit self-binding is available; implicit creation policy filters eligible types within that boundary.

## 3. Risks (Partially shared with Permissive Mode)

-   Graph expansion is implicit: adding a new constructor dependency to a transitive class silently enlarges the managed graph. In strict mode this requires an explicit binding decision; in semi-strict it is automatic and invisible in binding diffs.
-   Predicate and wildcard bindings can unexpectedly capture auto-expanded transitive types. In strict mode only explicitly named types can be captured by a predicate; in semi-strict any implicitly resolvable transitive type is also a candidate.
