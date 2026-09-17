# Scopes

Status: proposed (mechanism split). Nesting, blueprints, and seats are not implemented; a single live `DIBox` plus `BindingBox` modules and contextvar `@inject` are.

Scope is the phenomenon: an ownership boundary for resources that must be created and torn down together. It is not a class. `scope=` on `bind()`, named scope enums, and a second lifetime axis parallel to nesting are rejected. The word is reserved so a later concurrent primitive can still take it if needed.

## Problem

Dependencies have different lifetimes. A database pool lives for the process; a per-request transaction lives for one HTTP request; a UI session sits between login and logout. One flat container gives every instance the same lifetime, so either the developer builds short-lived objects by hand or everything becomes an accidental singleton.

Three mechanisms, three jobs. They must not share one occupancy story.

## When each is needed

One `DIBox` for the process: none of the three. Scripts, small apps, tests with a single container.

Nesting when the user can point at a block and say these resources die here, and they may use stuff that lives outside. HTTP request, pipeline stage, per-tenant then per-job, a CLI command that borrows the app. If everything dies together, nesting is unused. See [container_nesting.md](container_nesting.md) for `DIBox(parent=...)`, the resolution/placement rule, ownership, and the lifetime invariant.

A blueprint when the same kind of container is about to be copy-pasted: every request box, every GPU stage, a worker that must rebuild the graph from serializable config. A one-off `DIBox(parent=app)` with two binds in one middleware does not need one yet. Another process cannot take a live parent; it can take a reusable definition. See [container_blueprints.md](container_blueprints.md) for per-container setup, lifecycle orchestration, and cross-process reuse.

A seat when enter and exit are different handlers and some third function should still resolve against that box. UI session is the clean example. Web middleware that already does `async with` does not need a seat — the block is the occupancy. Pipeline stages neither. See [session_lifetime.md](session_lifetime.md). Occupancy must not live on the blueprint; it is not nesting.

Typical combinations, not a hierarchy:

- Web app: nesting (and `@inject` on the innermost box). A blueprint if the request box is a repeating shape. No seat.
- Pipeline in one process: nesting. A blueprint if stages repeat. No seat.
- Parallel workers: a blueprint (same container, no shared parent). Nesting only inside a worker. No seat.
- UI: nesting (session child of app) plus a seat (login/logout). A blueprint if the session box is a defined preset.

`@inject` is not a fourth lifetime mechanism. It only finds a box that is already active on this task ([entrypoints.md](entrypoints.md)). Nesting and blueprints produce boxes; a seat is what you need when nothing on the call stack entered one.

## Rejected as a parallel lifetime system

`scope=` on `bind()` is redundant with nesting. Where you bind is the lifetime. A second axis raises questions nesting already answers structurally (who manages enter/exit, how named scopes nest).

Named scope enums (`RequestScope`, `SessionScope`) are framework vocabulary. A generic library provides the primitives, not the words. If a name is needed, name the blueprint or the `BindingBox`.

A resolver stack / middleware chain on `Injector` is premature. A single resolver or the contextvar default covers the usual cases. Deferred; see [entrypoints.md](entrypoints.md) and [ideas.md](ideas.md).

## External references

Prior art that motivated rejecting declarative `scope=` in favor of nesting: [Dishka scopes](https://dishka.readthedocs.io/en/latest/advanced/scopes.html), [Guice scopes](https://github.com/google/guice/wiki/Scopes), [.NET DI lifetimes](https://learn.microsoft.com/en-us/dotnet/core/extensions/dependency-injection#service-lifetimes). Scenario evidence: [scopes_sketch.py](scopes_sketch.py).
