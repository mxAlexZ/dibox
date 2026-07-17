# Zero-Dependency Guard

Status: superseded by [Implicit Creation Policy](./implicit_creation_policy.md).

Related decisions:
- [Implicit Self-Binding](./implicit_self_binding.md): mechanism and mode boundaries this guard restricts.
- [Semi-Strict Resolution](./semi_strict_mode.md): applies ZDG to implicit transitive expansion below explicit roots.
- [Strict Mode](./strict_mode.md): explicit-binding policy; ZDG is only a guardrail.
- [Diagnostics and Introspection](./diagnostics.md): error locality and graph validation context.

## 1. Problem

Implicit self-binding is useful for concrete graph internals, but suspicious when the container only calls `Type()`. Zero-required-arg constructors are graph leaves: nothing is injected, defaults silently become configuration, and failures move to distant call sites.

## 2. Decision

A type is blocked from implicit self-binding when its constructor has no required parameters: zero parameters excluding `self`, or all parameters defaulted.

Explicit `box.bind(Type)` bypasses the guard by declaring default construction as container-owned behavior.

## 3. Rationale and examples

The guard targets types that need explicit user intent:

- Introspectable zero-dep types where default construction is semantically wrong: `Path()` produces `Path('.')`, `list()` produces `[]`, all-default user-defined classes silently use policy-level defaults.
- All-default services where defaults are policy: `RateLimiter(rps=100, burst=200)`.
- External resources needing configuration or lifecycle ownership: clients, pools, connections.

- `RateLimiter(rps=100, burst=200)` requires `box.bind(RateLimiter)` because it has no required parameters.
- `UserService(db: Database, cache: Cache)` still self-binds because the container resolves real dependencies.

Note: C builtins like `str` and `int` are non-introspectable on CPython — they cannot be silently auto-created because signature inspection raises an error first. For those types the guard provides a semantically clearer error, not protection against silent injection.

Interface or protocol choice remains a separate explicit-binding problem; ZDG does not choose implementations.

## 4. Trade-offs

Benefits:
- Blocks silent injection of introspectable zero-dep types (`Path`, `list`, all-default services).
- For non-introspectable builtins, surfaces a semantically meaningful error instead of a raw introspection failure.
- Improves error locality at missing-value leaves.
- Keeps bypass low-cost and explicit: `box.bind(Type)`.

Limitations:
- It is not a correctness guarantee; required-parameter classes can still be implicitly self-bound incorrectly.
- It does not cover interface or abstract-type ambiguity.
