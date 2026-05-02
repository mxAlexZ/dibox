# Strict Mode: Explicit Binding Policy

Status: Implemented. Container-level resolution modes are available, including strict mode.

This ADR isolates strict mode semantics and API.

Related decisions:
- [Implicit Self-Binding](./implicit_self_binding.md): read for the permissive fallback strict mode disables, and for why DIBox defaults to low-ceremony wiring.
- [Semi-Strict Resolution](./semi_strict_mode.md): read when explicit root ownership is needed without binding every concrete transitive class.
- [Zero-Dependency Guard](./zero_dependency_guard.md): read for the lightweight leaf-node guard used where implicit self-binding remains enabled.
- [bind(...) API](./bind_api.md): read for registration forms (`bind(T)`, `bind_many(...)`) that keep strict-mode boilerplate manageable.
- [Diagnostics and Introspection](./diagnostics.md): read for why a finite explicit graph improves validation, graph output, and failure locality.

## 1. Problem

Permissive resolution is convenient, but it can blur container ownership and defer configuration errors. In production and test environments, this creates avoidable risk:

- Unbound dependencies can be constructed implicitly instead of failing fast.
- The boundary between "container-managed" and "ad hoc constructed" types becomes unclear.
- Incomplete test module sets can silently resolve unintended implementations.

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
- Better test isolation: incomplete test modules fail instead of silently resolving unintended implementations.
- Better diagnostics leverage because the managed graph is finite and explicit.

Costs:
- Requires explicit registration for each managed root/type.
- Adds modest setup boilerplate, usually mitigated by `bind(T)` and `bind_many(...)`.

Boundaries:
- Strict mode is not a substitute for explicit interface-to-implementation mappings; abstract or protocol dependencies still require explicit bindings.
- If explicit roots plus permissive transitive expansion is needed, use semi-strict mode rather than extending strict mode semantics.
