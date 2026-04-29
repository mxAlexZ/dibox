# EP: Diagnostics and Introspection

**Status**: Proposed

This document outlines features designed to improve the debuggability and observability of the DIBox container. Good diagnostics are essential for making the dependency injection process transparent and easy to troubleshoot.

-   See also: [Strict Mode](./strict_mode.md) (for explicit-binding fail-fast policy), [Implicit Self-Binding](./implicit_self_binding.md) (for permissive fallback limits), [Entrypoints](./entrypoints.md) (for where resolution is triggered).

---

## 1. Meaningful Errors: The Resolution Stack

A common failure in DI systems is an error message that points to a low-level dependency, offering no clue about the actual misconfiguration higher up the chain.

### The Problem

A request for `StorageClient` fails because its dependency, `AppConfig`, was never bound. The container, trying to be helpful, attempts to construct `AppConfig` itself, which in turn fails when it tries to construct a `str` for the `db_url` parameter.

Current error: `Cannot construct type 'str' with zero arguments.` (Useless)

### The Solution: Resolution Stack Tracking

During any resolution process (`provide`, `call`, etc.), the container will maintain an internal stack of the types it is currently trying to build.

If resolution fails, the full stack is included in the error message, providing a complete trace from the initial request to the point of failure.

Proposed error:
```
DIBoxResolutionError: Cannot resolve dependency 'db_url: str' for 'AppConfig'.
Value types like 'str' cannot be auto-constructed.
Did you forget to bind 'AppConfig'?

Resolution path:
  - StorageClient
  - AppConfig
  - str  <-- failure
```

This immediately tells the developer not only what failed (`str`), but why the container was trying to build it (`AppConfig` -> `StorageClient`), pointing directly to the likely source of the misconfiguration.

---

## 2. Cycle Detection

A direct benefit of tracking the resolution stack is robust and immediate detection of circular dependencies.

### The Problem

`ServiceA` depends on `ServiceB`, and `ServiceB` depends on `ServiceA`. This would currently result in a `RecursionError`.

### The Solution

Before attempting to resolve a type, the container checks if that type is already present in the current resolution stack. If it is, a cycle has been detected.

Proposed error:
```
DIBoxCycleError: Circular dependency detected.

Resolution path:
  - ServiceA
  - ServiceB
  - ServiceA  <-- cycle
```

This provides a clear, immediate, and actionable error, pinpointing the exact services involved in the loop.

---

## 3. Proactive Validation: Introspection APIs

The following APIs are proposed to allow for proactive, startup-time validation of the container's configuration.

### 3.1. `box.validate()`

Eagerly verify the container's configuration without fully instantiating every object. Traverses the dependency graph of registered components and reports missing bindings and cycles.

### 3.2. `box.graph()`

Generate a representation of the dependency graph for visualization or analysis. Output could be a simple dictionary or a format compatible with tools like Graphviz.

### 3.3. Resolution mode impact

Resolution mode determines how much of the graph is statically knowable.

Strict — the managed type set is fully known from explicit bindings. Both `validate()` and `graph()` can operate comprehensively without any runtime resolution.

Semi-strict — explicit roots are known, but transitive expansion can introduce nodes that were never explicitly bound. Whether those nodes can be pre-computed statically (by following type hints from the roots) or are only observable at runtime depends on the introspection surface design (see section 4).

Permissive — the set of implicitly resolvable types is open-ended; full static analysis is impossible. Both APIs fall back to entry-point-driven traversal: `box.validate(from_entrypoints=[WebApp, Cli])`. Less exhaustive, but still catches misconfiguration within the named subgraphs.

## 4. Open Questions

-   Semi-strict introspection surface: should auto-expanded transitive nodes be visible only as derived runtime nodes in graph/diagnostic output, or also materialized as generated bindings in the registry? Materializing them makes `validate()` and `graph()` fully pre-computable for semi-strict, but adds implicit registry state that was never explicitly declared.
