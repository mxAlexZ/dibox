# Strict Mode: Explicit Binding Policy

Status: Implemented. Container-level resolution modes are available, including strict mode.

This ADR isolates strict mode semantics and API. Permissive implicit self-binding and its guard proposal are tracked in [Implicit Self-Binding and Zero-Dependency Guard](./implicit_self_binding.md).

Related ADRs:
- [Implicit Self-Binding and Zero-Dependency Guard](./implicit_self_binding.md): defines the permissive fallback behavior that strict mode intentionally disables.
- [bind(...) API](./bind_api.md): defines `bind(T)` and `bind_many(...)`, which reduce strict-mode registration noise.
- [Diagnostics and Introspection](./diagnostics.md): documents why strict mode enables complete validation and graph-level guarantees.
- [Semi-Strict Resolution](./semi_strict_mode.md): explores a middle policy that keeps strict-style explicit roots while relaxing transitive expansion.

## 1. Problem

Permissive resolution is convenient, but it can blur container ownership and defer configuration errors. In production and test environments, this creates avoidable risk:

- Unbound dependencies can be constructed implicitly instead of failing fast.
- The boundary between "container-managed" and "ad hoc constructed" types becomes unclear.
- Missing test overrides can silently fall back to real implementations.

Strict mode exists to make container policy explicit and failure behavior immediate.

## 2. Strict Mode Contract

Strict mode is enabled with `DIBox(mode="strict")`.

Contract:
- Only explicitly registered bindings are resolvable.
- Resolving an unbound type fails immediately.
- The managed dependency set is exactly what is declared via `bind(...)`/`add_bindings(...)`.
- Implicit self-binding fallback is disabled.

Default `DIBox(mode="permissive")` remains the low-ceremony option, but strict mode is the production/test baseline when explicit ownership and fail-fast behavior are required.

## 3. Trade-offs and Boundaries

Benefits:
- Stronger production safety through fail-fast behavior.
- Clear container ownership boundary.
- Better test isolation: missing mocks fail instead of silently resolving real implementations.
- Better diagnostics leverage because the managed graph is finite and explicit.

Costs:
- Requires explicit registration for each managed root/type.
- Adds modest setup boilerplate, usually mitigated by `bind(T)` and `bind_many(...)`.

Boundaries:
- Strict mode is not a substitute for explicit interface-to-implementation mappings; abstract or protocol dependencies still require explicit bindings.
- If explicit roots plus permissive transitive expansion is needed, use [Semi-Strict Resolution](./semi_strict_mode.md) rather than extending strict mode semantics.
