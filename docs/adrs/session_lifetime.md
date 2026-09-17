# Session lifetime (seats)

Status: proposed.

Related ADRs:
- [scopes.md](scopes.md): lifetime problem and when a seat is the mechanism versus nesting or a blueprint.
- [container_blueprints.md](container_blueprints.md): a seat holds a box created by a blueprint (setup, lifecycle, close); it does not create boxes.
- [container_nesting.md](container_nesting.md): a seated box may be a child of the app; placement of session types uses nesting rules, not occupancy.
- [entrypoints.md](entrypoints.md): `@inject` finds the innermost active container on this task; a seat is what you need when nothing on the call stack entered one.
- [philosophy.md](philosophy.md): DI stays at the composition edge; decorating every UI callback fights that.
- [factories.md](factories.md): runtime object creation inside business logic is a separate problem from seating.

## Problem

Some lifetimes are not a stack frame. A UI session starts at login and ends at logout in another handler, with no `async with` around the interval. Between those two calls the box must stay live, and later callbacks need to find it.

Without a seat, the application stashes the box on a global, the widget tree, or `app.state`, and every handler fishes it out — or `@inject` quietly resolves from the app and session types get created in the wrong place.

## What a seat is

A named occupancy of one live box of a given kind: remember it, find it later, drop it from a different call. The seat tracks the occupant; lifecycle attach/detach stays on the blueprint.

Occupancy must stay off the blueprint. Putting `current` / `exit` on it would make `session.exit()` read as "end the session" rather than "end this occupant," and would make concurrently created boxes a policy fight.

## Occupancy policy

Seated UI often wants "second enter is an error, or it replaces the previous." Independent boxes created from the same blueprint must not inherit that rule. The policy is a product of the seat, not the blueprint.

Candidates, none locked: refuse re-enter while occupied in this context; replace and close the previous (leak risk if something still holds it); allow many live boxes and require an explicit handle. Keeping both live only requires retaining each created `DIBox`; it does not need a seat.

Contextvars already isolate occupancy across tasks. Same-task `asyncio.gather` of two enters shares one context and would clobber; that limitation already applies to `@inject`. Ambient inject cannot see two boxes at once; that is what holding the `DIBox` is for.

## Non-invasiveness

DI belongs at the composition edge ([philosophy.md](philosophy.md)). A FastAPI route is an entrypoint; a UI click handler usually is not, and decorating dozens of clicks with `@session.inject` (or even `@inject`) makes the widget layer a second composition root. The session composition root is login. A blueprint lifecycle that does `ui.attach(fancy)` is the non-invasive path: handlers talk to objects they already have.

`@session.inject` remains open, with a lean against it as the primary API for callbacks. If a UI framework is callback-shaped with no widget tree to attach to, `@inject` plus activating the seated box at login is equivalent to a route; a second decorator keyed to the seat is not required. The app's missing-binding policy should reject session types so using the wrong current container fails instead of implicitly creating them. Otherwise, avoid injection in those handlers.

Logout mentioning the box (or the seat) is allowed: logout is an entrypoint.

## Construction sketch

Names are placeholders. The seat is occupancy around a blueprint, not a spawn factory.

```python
# wiring — blueprint creates; seat retains
session = hold(app.blueprint())

async def on_login_ok(info: SessionInfo, workspace: Workspace) -> None:
    await session.enter(info, workspace)

async def on_logout() -> None:
    await session.exit()
```

Who stores the occupant (library seat versus `app.state.session_box = box`) is open. User-managed storage is not a cop-out when blueprint creation returns a box that can be closed later; a library seat is sugar for the single-occupant UI case and must not be mixed back onto the blueprint.

## Open questions

- Occupancy API shape: `enter` / `exit` / `current` on a seat object, versus the application holding the `DIBox` and calling close.
- Concurrent activations of the same seat: error, replace, or both live. This policy lives on the seat, not the blueprint.
- `@session.inject` versus lifecycle-attach for callbacks (lean: attach; `@inject` + activate if the framework is callback-only).
- Naming (Hold, Seat, Latch, Focus).
- Whether `enter` sets the task-local current container used by `@inject`, only the seat's occupant, or both.
- No-argument exit when the logout site has no box in hand: that is a seat feature; a lexical flow can still close the box returned by blueprint creation.
