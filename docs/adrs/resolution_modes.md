# EP: Resolution Modes

**Status**: Partially implemented — `strict` flag is implemented; zero-dependency guard (§3) is still proposed.

This document defines the strategies the container uses to resolve dependencies. It proposes a configurable system that allows developers to choose between convenience and strictness.

-   **See also**: [EP: Entrypoints](./entrypoints.md) (for how `call()` and `@inject` trigger resolution), [EP: Diagnostics](./diagnostics.md) (for error reporting).

---

## Terminology

Two mechanisms are often conflated under "auto-wiring":

- *Type-hint wiring* — the container reads a type's constructor signature and resolves each annotated parameter. Always active; not configurable.
- *Implicit self-binding* — when no explicit `bind()` call exists for a type, the container treats the type itself as its own factory. This is the actual policy question.

The rest of this document is about implicit self-binding and how to control it.

---

## 1. Core Concepts

DIBox supports two fundamental resolution strategies. The choice between them is the most significant policy decision a developer makes when configuring a container.

### 1.1. Implicit Self-Binding (Permissive Mode)

-   What it is: If no explicit binding is found for a concrete type, the container attempts to construct it by resolving its dependencies.
-   Example: `await box.provide(MyService)` works without `box.bind(MyService)`.
-   Pros:
    -   Low Friction: Ideal for simple projects, prototypes, and internal services where there is no ambiguity. Reduces boilerplate.
    -   Easy Onboarding: Aligns with the "zero-configuration" goal for common cases.
-   Cons:
    -   Silent Failures: A missing configuration (e.g., for `AppConfig`) can lead to the container constructing objects with incorrect, default-initialized data (`str("")`, `int(0)`), causing runtime errors far from the source of the problem.
    -   Ambiguous Contract: It's unclear if the container *manages* a type or just *constructs* it on demand.

### 1.2. Explicit Binding (Strict Mode)

-   What it is: The container will only resolve types that have been explicitly registered via `box.bind()`. Any attempt to provide an unbound type results in an immediate error.
-   Example: `await box.provide(MyService)` fails unless `box.bind(MyService)` was called.
-   Pros:
    -   Production Safety: Eliminates silent misconfiguration failures. Errors are loud, immediate, and easy to diagnose.
    -   Clear Intent: The set of managed types is explicitly declared. The container's configuration serves as documentation.
    -   Predictable Testing: Forgetting to provide a mock for a dependency in a test results in an immediate failure, preventing tests from accidentally using real implementations.
    -   Enables Introspection: Makes container validation (e.g., `box.validate()`) and dependency graph visualization possible. See [EP: Diagnostics](./diagnostics.md).
-   Cons:
    -   Minor Boilerplate: Requires one `box.bind(T)` call for each service `T`.

---

## 2. Proposed API: Configurable Modes

Instead of enforcing one policy, DIBox will make the resolution strategy a configurable choice on the container itself. This aligns with the "Progressive Disclosure of Complexity" principle.

### 2.1. Container-Level `strict` Flag

The `DIBox` constructor accepts a `strict` flag:

-   `DIBox(strict=False)` (Default)
    -   Behavior: Uses Implicit Self-Binding.
    -   Use Case: Recommended for initial development, small scripts, and prototypes where speed and convenience are prioritized.

-   `DIBox(strict=True)`
    -   Behavior: Enforces Explicit Binding.
    -   Use Case: Recommended for production applications, libraries, and mature codebases where safety, predictability, and clear intent are critical.

This gives projects a clear migration path from permissive to strict as they mature, without changing the fundamental DI paradigm.

### 2.2. Per-Call Overrides (Idea)

For more granular control, the container-wide `strict` setting could potentially be overridden at the entrypoint level.

-   `await box.provide(Service, strict=True)`
-   `await box.call(func, strict=False)`

This would allow mixing resolution strategies, for instance using a globally strict container but allowing a specific `call` to operate permissively for a one-off script.

This idea is documented for completeness but is not part of the immediate implementation plan. The primary mechanism for controlling resolution is the container-wide `strict` flag. The need for per-call overrides will be re-evaluated based on future use cases.

---

## 3. Proposed: Zero-Dependency Guard for Permissive Mode

To reduce the risks of the default `strict=False` mode, a safeguard is proposed to prevent the most common and problematic cases of unintended construction.

-   Rule: The container will refuse to auto-construct any type that can be initialized with zero required arguments.
-   Mechanism: It inspects the type's `__init__` signature. If all parameters have defaults (or there are no parameters), it is blacklisted from implicit self-binding.
-   What this prevents:
    -   Value Types: `str()`, `int()`, `list()`, `dict()`, `Path()`.
    -   Zero-Arg Services: `InMemoryCache()`.
    -   All-Default Services: `RateLimiter(rps=100, burst=200)`.
-   Effect: In permissive mode, a missing binding for a configuration object like `AppConfig(db_url: str)` will no longer silently succeed by creating an `AppConfig("")`. Instead, it will fail when it attempts to resolve the `str` dependency, as `str` has no required constructor arguments. The error is still at the leaf, but it is no longer silent.
-   Limitation: This is a guardrail, not a complete solution. It does not prevent implicit self-binding for types that have required parameters. Only `strict=True` provides a full guarantee against misconfiguration.

The all-defaults case (`RateLimiter(rps=100, burst=200)`) deserves a note: requiring `box.bind(RateLimiter)` for such a type is a mild forcing function, not a penalty. When there are no dependencies to wire, the container adds no construction value over calling the constructor directly, so making the intent explicit costs almost nothing and keeps the container's managed set unambiguous.

Implementation draft:
```python
def _is_autowireable(t: type) -> bool:
    try:
        sig = inspect.signature(t)
    except (ValueError, TypeError):
        return False  # C extensions, special forms — treat as blacklisted
    return any(
        p.default is inspect.Parameter.empty
        and p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        for p in sig.parameters.values()
    )
```
---

## 4. Summary of Trade-offs

A. `strict=False` (Permissive)
-   Getting Started: Faster
-   Debuggability: Fair (with guard + diagnostics)
-   Production Safety: Lower
-   Best Practice: Encourages convenience

B. `strict=True` (Explicit)
-   Getting Started: Small overhead
-   Debuggability: Excellent
-   Production Safety: Higher
-   Best Practice: Encourages explicit intent

This model allows developers to make a conscious choice, starting with convenience and opting into strictness as the application's requirements evolve.
