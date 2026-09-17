# Container nesting

Status: proposed.

Related ADRs:
- [scopes.md](scopes.md): lifetime problem and when nesting is the mechanism to reach for versus blueprints or seats.
- [missing_binding_policy.md](missing_binding_policy.md): authorizes implicit construction; does not choose which nested container owns the instance.
- [implicit_self_binding.md](implicit_self_binding.md): supplies the inferred construction recipe whose placement this ADR decides.
- [container_blueprints.md](container_blueprints.md): a blueprint can create many children of a live parent; nesting is the parent-child relationship those children enter.
- [session_lifetime.md](session_lifetime.md): occupancy across disconnected calls; not a second nesting rule.
- [entrypoints.md](entrypoints.md): controls when a nested container becomes task-local current for `@inject`.
- [scopes_sketch.py](scopes_sketch.py): pipeline stages, tenants, jobs, CLI commands as lexical nesting evidence.

## Problem

Some objects must live longer than others, while short-lived objects still depend on them. A database pool outlives the request that uses it. One flat container gives every instance the same lifetime, so the short-lived object becomes an accidental singleton or is built by hand outside DI.

## Decision

`DIBox(parent=...)` would be a child lifetime: it can resolve through the parent, owns its own instances, and closes those instances when the child's block ends. The caller holds that block (`async with`). Each container would close only what it owns. A child would point at its parent for lookup; the parent would not track children. A child that outlives its parent is a usage error.

## Placement

Closing is per container, so resolution has to answer a second question: which container owns the instance?

Wrong ownership is a teardown bug. If a parent-owned object depends on something the child created, the child closes that dependency while the parent still holds it. The constraint: every dependency lives in the same container as its dependent, or in an ancestor.

### Explicit bindings

An explicit binding declares how to construct the instance and which container owns it. Lookup would walk from the requested container toward the root and stop at the nearest matching binding. That container owns the instance, even if the request started on a child, and it resolves the rest of that instance's dependencies in the same container.

A child may bind the same type as a parent; lookup then stops at the child. Parent-owned instances still resolve their dependencies from the parent, so a parent object cannot keep a child-owned dependency.

If child-owned `A` depends on parent-owned `C`, and `C` depends on `B` while the child also binds `B`, `C` is built as a parent object and uses the parent's `B`. Diagnostics should name the boundary and the child's unused binding.

### Implicit construction

When lookup finds no binding, the container that is resolving the type would construct it implicitly, or fail if its missing-binding policy forbids that ([implicit_self_binding.md](implicit_self_binding.md), [missing_binding_policy.md](missing_binding_policy.md)). It would not ask a parent to create the instance or to authorize it.

This keeps the missing-binding policy out of lifetime decisions, which are not its job. If a child could delegate creation upward, its own policy would place objects into another container's lifetime, and the lifetime of a shared implicit instance would depend on who resolved the type first. Keeping creation on the resolving container also satisfies the close-order constraint, since a parent-bound service already resolves its own internals there.

The cost is that sibling children each create their own copy of an expensive unbound type.

## Open questions

- Whether to adopt this container-local implicit placement (lean: yes).
- Whether a child inherits the parent's missing-binding policy by default (lean: inherit, overridable).
- Whether a child blueprint is created only through a live parent's method or also through `Blueprint(parent=...)`.
- Whether `validate()` warns when sibling containers implicitly create the same type.
- Exact diagnostic when a parent-owned dependency ignores a child's binding of the same type.
