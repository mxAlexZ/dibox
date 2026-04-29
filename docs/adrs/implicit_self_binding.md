# Implicit Self-Binding, Permissive Mode and Zero-Dependency Guard

Status: Partially implemented. The zero-dependency guard is proposed and not implemented.

This ADR is scoped to permissive resolution behavior. Strict mode policy and API are tracked in [Strict Mode](./strict_mode.md).

Related ADRs:
- [Strict Mode](./strict_mode.md): defines explicit binding semantics, the safety baseline this ADR contrasts with.
- [Entrypoints](./entrypoints.md): explains how permissive fallback affects `provide()`, `call()`, and decorator-driven resolution.
- [Diagnostics and Introspection](./diagnostics.md): explains why permissive fallback weakens exhaustive validation and graph guarantees.
- [Semi-Strict Resolution](./semi_strict_mode.md): proposes explicit roots with implicit transitive expansion.

## 1. Problem

Implicit self-binding is useful for fast onboarding, but it can hide missing configuration. When an unbound dependency is a zero-arg or all-default constructor, permissive resolution can silently instantiate the wrong object and defer failure to a distant call site.

The ADR goal is to keep permissive DX while reducing the most error-prone silent-success cases.

## 2. Current behavior: implicit self-binding

Two mechanisms are often conflated under "auto-wiring":

- Type-hint wiring: the container reads constructor annotations and resolves typed parameters. This behavior is always on.
- Implicit self-binding: when no explicit `bind()` entry exists for a concrete type, the container treats that type as its own factory.

In permissive mode (the default), implicit self-binding is enabled:

- `await box.provide(MyService)` can succeed without `box.bind(MyService)`.
- This keeps setup friction low for prototypes, scripts, and small internal services.

The downside is policy ambiguity: the container may construct types that were never intended to be container-managed.

## 3. Proposed: Zero-Dependency Guard

To reduce silent misconfiguration in permissive mode, add a guard that blocks implicit self-binding for types with zero required constructor parameters.

Rule:
- A type is not eligible for implicit self-binding when its constructor has no required parameters.

Practical impact:
- Blocks value-like leaf types (`str`, `int`, `list`, `dict`, `Path`) from silent construction.
- Blocks zero-arg and all-default service constructors from being silently materialized.
- Preserves permissive behavior for concrete types with real required dependencies.

Example failure shift:
- Missing binding for `AppConfig(db_url: str)` no longer silently succeeds through `str("")` construction. Resolution fails at `str` as a blocked leaf, producing a visible misconfiguration signal.

All-default constructors (`RateLimiter(rps=100, burst=200)`) are intentionally blocked from implicit creation. Requiring `box.bind(RateLimiter)` in that case is a low-cost intent declaration because the container contributes little construction value for zero-required-arg types.

## 4. Trade-offs and boundaries

Benefits:
- Preserves zero-config ergonomics for common concrete service graphs.
- Eliminates a high-frequency silent-failure class in permissive mode.

Limitations:
- This is a guardrail, not a full strictness guarantee.
- Types with required parameters can still be implicitly self-bound.
- Full "only explicitly managed types resolve" semantics remain the role of [Strict Mode](./strict_mode.md).

## 5. Summary

Permissive mode remains the onboarding-optimized default. The zero-dependency guard is the minimum safety filter needed to keep that default viable without pretending it offers strict-mode guarantees.
