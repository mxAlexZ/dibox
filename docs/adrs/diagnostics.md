# EP: Diagnostics and Introspection

**Status**: Proposed

This document outlines features designed to improve the debuggability and observability of the DIBox container. Good diagnostics are essential for making the dependency injection process transparent and easy to troubleshoot.

-   See also: [EP: Resolution Modes](./resolution_modes.md), [EP: Entrypoints](./entrypoints.md).

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

Purpose: Eagerly verify the container's configuration without fully instantiating every object. It traverses the dependency graph of registered components and reports any missing bindings or cycles.

Behavior depends on the resolution mode:

In `DIBox(strict=True)` mode:
-   `validate()` is powerful and comprehensive. Since the set of managed types is explicitly known via `bind()`, the method can check the integrity of the entire graph.
-   All missing bindings and cycles are caught at startup time before any services are constructed.

In `DIBox(strict=False)` mode:
-   The task is harder. The set of potentially resolvable types is infinite, so a full validation is impossible.
-   `validate()` would operate on a best-effort basis, likely by checking only the explicitly bound types and their direct dependencies.
-   Alternatively, the user could provide entry-point types to traverse from: `box.validate(from_entrypoints=[WebApp, Cli])`.
-   This approach is less complete but still provides value: catching misconfiguration in the parts of the graph the user explicitly names.

### 3.2. `box.graph()` (Idea)

Purpose: Generate a representation of the dependency graph for visualization or analysis.

Behavior:
-   In `strict=True` mode: Straightforward. The complete graph is known and can be fully visualized.
-   In `strict=False` mode: Same limitations as validate(). Requires a starting point or entry-point list for traversal.
-   Output could be a simple dictionary or a format compatible with tools like Graphviz.

---

## 4. The Impact of Resolution Mode on Diagnostics

The choice of resolution mode (`strict` vs. `permissive`) directly affects the effectiveness of these diagnostic tools.

With `strict=True`, all diagnostics are powerful and comprehensive. The set of managed types is known and finite, making validation and visualization trivial. This is a primary benefit of using explicit binding: errors and misconfiguration are caught early and reported clearly.

With `strict=False`, the infinite possibility of implicit self-binding makes these tools harder to implement. They must operate on a best-effort basis, validating only what the user explicitly names. While still valuable, they lack the exhaustiveness and certainty of strict mode. This is both a design limitation and a practical argument for using explicit binding in production systems.
