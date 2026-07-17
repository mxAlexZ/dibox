# Implicit Self-Binding and Permissive Defaults

Status: implemented

This ADR defines implicit self-binding as a resolution mechanism. It also documents full permissive mode because DIBox does not yet have a separate permissive-mode ADR.

Related decisions:
- [Implicit Creation Policy](./implicit_creation_policy.md): filters which unbound concrete types may use implicit self-binding within the mode boundaries defined here.
- [Semi-Strict Resolution](./semi_strict_mode.md): explicit roots with implicit self-binding for graph internals when permissive roots are too open.
- [Strict Mode](./strict_mode.md): fully explicit ownership boundary for production and test safety.
- [Diagnostics and Introspection](./diagnostics.md): why open-ended implicit graph expansion limits validation and graph guarantees.
- [Entrypoints](./entrypoints.md): how resolution policy affects `provide()`, `call()`, and decorator-driven injection.

## 1. Motivation: zero-config concrete service graphs

Dependency graphs are dominated by concrete service classes whose constructors already describe the dependency structure. If `UserService` requires `UserRepo` and `Logger`, there is usually no extra decision to record for those concrete intermediate types. Requiring `bind(UserService)`, `bind(UserRepo)`, and every similar class turns type hints into duplicated registration boilerplate.

Implicit self-binding exists to remove that noise inside the graph. Once a concrete class is part of resolution, DIBox can use its constructor as the factory and follow required annotated parameters recursively.

Full permissive mode extends the same convenience to requested roots: a user can ask for a concrete root without binding it first. This is the easiest onboarding path for scripts, prototypes, small apps, and internal services where setup friction is the largest adoption cost.

## 2. Terminology

Type-hint wiring means inspecting constructor annotations and resolving required parameters from the container.

Implicit self-binding means that when no explicit binding exists for a concrete class, DIBox treats that class as its own factory.

Resolution mode decides where implicit self-binding is allowed: permissive mode allows it for roots and transitive dependencies; semi-strict mode allows it only below explicit roots; strict mode disables it. Implicit creation policy then decides whether a particular unbound concrete type is eligible within those boundaries.

"Auto-wiring" is an overloaded label for both ideas, so this ADR uses the precise terms above.

## 3. Resolution-mode contract

Across modes, explicit bindings win over implicit behavior. When implicit self-binding is allowed for a concrete class:

- DIBox constructs the class directly if no binding exists.
- Required annotated constructor parameters are resolved recursively.
- Missing annotations, non-concrete requests, and unsupported special forms fail resolution.
- Created instances are container-managed after construction.

Mode boundaries:

- Permissive mode: implicit self-binding applies to requested roots and transitive dependencies. This makes `await box.provide(MyService)` valid without `box.bind(MyService)` when `MyService` is a concrete class with resolvable annotated dependencies.
- Semi-strict mode: requested roots must be explicitly bound, but transitive concrete dependencies may still self-bind. This preserves the main ergonomics benefit for graph internals while making ownership explicit at the boundary.
- Strict mode: implicit self-binding is disabled. Every resolvable type must be explicitly bound.

## 4. Why permissive is the default, and when semi-strict fits

Full permissive mode follows progressive disclosure of complexity: useful first, stricter later. It lets DIBox act as a wiring tool before it becomes a policy tool.

Users should bind explicitly where there is a real decision: configuration values, secrets, interface implementations, lifecycle-managed resources, test modules, or named variants. For ordinary concrete classes whose constructor signature fully determines their dependencies, implicit self-binding records no additional intent.

Semi-strict mode is the main mitigation when full permissive roots become too open. It keeps the valuable part of implicit self-binding — automatic wiring for concrete graph internals — while requiring explicit root declarations for ownership, tests, and production review.

## 5. Boundaries and risks

Full permissive mode keeps the graph open-ended. That has costs:

- Container ownership is less explicit; an unbound concrete class may become managed because it was requested or appeared transitively.
- Adding a constructor dependency can silently expand the graph.
- Missing configuration can be hidden when a leaf type is constructable with defaults.
- Exhaustive validation and graph introspection are weaker because the managed set is not closed up front.

The default implicit creation policy blocks common value-type leaves while allowing ordinary zero-dependency application classes. Semi-strict mode reduces open-root risk while preserving implicit transitive wiring. Strict mode disables implicit self-binding entirely.

## 6. Summary

Implicit self-binding is the mechanism that lets concrete service graphs be wired from type hints without duplicating the graph in binding declarations. Full permissive mode applies it at roots for easy onboarding; semi-strict mode applies it inside explicit roots for safer growth. Its purpose is not to avoid explicit bindings everywhere, but to reserve them for places where user intent cannot be inferred from the constructor.
