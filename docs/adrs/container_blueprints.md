# Container blueprints

Status: proposed.

Related ADRs:

- [scopes.md](scopes.md): lifetime problem and when a blueprint is the mechanism versus nesting or a seat.
- [binding_modules.md](binding_modules.md): `BindingBox` holds binding rules poured into a live container; a blueprint produces live containers.
- [container_nesting.md](container_nesting.md): containers created from a child blueprint would nest under a live parent; nesting rules are not restated here.
- [session_lifetime.md](session_lifetime.md): a seat may retain a blueprint-created box across disconnected calls; the blueprint does not track live boxes.
- [sync_async.md](sync_async.md): resolving lifecycle dependencies is async, although constructing and configuring a `DIBox` is synchronous.
- [ideas.md](ideas.md): constructing every known binding at container creation is separate from the lifecycle hook's selective eager dependencies.
- [scopes_sketch.py](scopes_sketch.py): Ray workers rebuild a container from serializable config in another process — the cross-process case a blueprint covers and nesting cannot.



## Problem

The same container shape is often constructed repeatedly—for example, one box per request. Rebuilding its bindings and policy at every construction site duplicates shareable configuration and burdens each entrypoint with setup boilerplate.

`BindingBox` already repeats the bind list. A blueprint would cover the rest of the construction site: parent, policy, values known only when each box is created, and work spanning its lifetime. Another process cannot take a live parent; it can rebuild from an importable definition.

## Decision

A blueprint would be a named, importable, deferred container definition. It would capture an optional parent, reusable bindings and policy, and optional hooks for per-container setup and lifecycle orchestration.

Each use would create an independent `DIBox`. One blueprint could create many containers, concurrently in different tasks or as independent roots in other processes.

The blueprint would not track a current container. Each created box has an independent lifecycle and may coexist with other boxes from the same definition.

## Per-container values

Some bindings depend on values available only when a container is created. For example, `SessionInfo` is specific to one login. Adding these values after exposing the box creates a race with dependency resolution.

The blueprint would accept a synchronous setup hook that receives the new box and caller-supplied values. It would be the last code allowed to bind and would finish before the box becomes resolvable.

The setup hook is synchronous and cannot take injected parameters. Injection would require `provide` before setup is complete. The entrypoint performs I/O and fetches inputs first; the hook only binds them.

## Lifecycle orchestration

Some work spans the container's lifetime without belonging to one managed instance—for example, attaching a service to a window and undoing that on close. Putting this in an instance's `close()` couples application orchestration to that instance, while scattering it across callbacks fragments the composition.

The blueprint would accept one generator lifecycle hook. Its autowired parameters define which dependency graphs start eagerly. Before running the hook body, the container would `provide` those parameters and run their start hooks. Code before yield performs setup; code after yield performs teardown. Importing the blueprint starts nothing.

Driving the lifecycle is async even when the hook is written as a sync generator because resolving its dependencies may be async. Synchronous resolution is a separate concern ([sync_async.md](sync_async.md)).

## Container creation and teardown

Creating a container from a blueprint would be one async operation for the caller. Internally it would:

1. synchronously create the `DIBox`, copy its parent, bindings, and policy, and run the setup hook;
2. resolve the lifecycle parameters and run setup to yield, if a lifecycle exists;
3. return the ready container.

This ordering prevents resolution before per-container values are bound and prevents returning a box with pending lifecycle setup. The uniform API requires `await` even when no lifecycle is configured, but keeps the internal phases out of the user model.

The new container would not become task-local current automatically; entrypoints control that ([entrypoints.md](entrypoints.md)).

Close remains async because one managed instance may require `aclose`. Lifecycle teardown runs before managed instances close in LIFO order. If lifecycle setup fails before yield, dependencies created for the hook still close, but the generator is not resumed as if it had yielded.

## Creating blueprints

A live `DIBox` would expose a method that returns a child blueprint parented to that box (`app.mint()` / `app.blueprint()`—name unresolved). `Blueprint()` without a parent would define a deferred root. The method is the usual child recipe; the constructor supports cases such as a CLI that creates its root container later.

`Blueprint.blueprint()` (a child recipe parented to whatever the outer blueprint creates) is rejected: the outer blueprint can create N containers, so the child would have N possible parents. Child recipes attach to a live box.

## Cross-process

A parent `DIBox` cannot cross a serialization boundary; config and a blueprint can. Each worker creates a local container, and nesting stays local to that process. The blueprint is the contract between driver and worker, not a distributed container.

## Illustrative sketch

Names below are placeholders.

```python
session = app.blueprint()
session.bind(FancyService)

@session.setup
def configure_session(box: DIBox, info: SessionInfo, workspace: Workspace) -> None:
    box.bind(SessionInfo, info)
    box.bind(Workspace, workspace)

@session.lifecycle
async def run_session(fancy: FancyService):
    ui.attach(fancy)
    yield
    ui.reset_to_login()

box = await session.create(info, workspace)
await box.close()
```

## Open questions

- Concept and API name (Mint, Preset, Blueprint, method on `DIBox`).
- How setup inputs such as `info` and `workspace` in the example are declared and statically checked without reducing `create(...)` to an untyped argument contract.
