# DIBox Design Review Split Index

Documentation for giving LLMs and humans a clear context of the design decisions, trade-offs, and open questions.

The documents can contain unpolished ideas. It is not part of the public documentation.

See [adr_concept.md](adr_concept.md) for ADR purpose and lifecycle; see repository instructions for retrieval and update workflow.

## Index
 - [adr_concept.md](adr_concept.md): why ADRs exist, information economics, delivery leverage, lifecycle stages, and why maintenance matters
 - [bind_api.md](bind_api.md): `bind(...)` forms, generator/contextmanager factories, setup-teardown resources, rejected fluent APIs
 - [binding_modules.md](binding_modules.md): `BindingBox` modules, `add_bindings`, precedence/overrides, module naming, module-level cycle detection
 - [diagnostics.md](diagnostics.md): Resolution stack errors, cycle detection, `validate()`/`graph()`, strict vs permissive diagnostics coverage
 - [entrypoints.md](entrypoints.md): `@inject`, `Injected[T]`, signature rewriting, `container.call()`/`partial()`, `Injector`, mode-dependent behavior
 - [package_binding.md](package_binding.md): `PackageBindingBox` scanning, auto-self-binding filters, dataclass exclusion, zero-dependency guard, lazy import caveats
 - [named_bindings.md](named_bindings.md): Argument-name matching limits, `Annotated` + `Named`/`Token`, third-party integration, `NewType` alternative
 - [scopes.md](scopes.md): Scope lifetimes via `DIBox(parent=...)`, ownership/shadowing rules, resolver/contextvar integration, `scope=` trade-offs
 - [scopes_sketch.py](scopes_sketch.py): Pipeline/Ray scope scenarios, app-run-stage nesting, `@inject` contextvars, `container.call()`, module reuse
 - [resolution_modes.md](resolution_modes.md): Implicit self-binding vs explicit binding, `strict` flag, zero-dependency guard, safety/convenience trade-offs
 - [factories.md](factories.md): Proposal for call-time factory args, container-aware factories, dynamic/context-driven dependency creation
 - [sync_async.md](sync_async.md): Sync-mode limitations and proposals for `get()`/`provide_sync()` plus sync factory behavior
 - [philosophy.md](philosophy.md): Progressive disclosure of complexity: zero-config defaults with explicit advanced controls
 - [ideas.md](ideas.md): Roadmap and deferred ideas: overrides, startup initialization, resolver args, signature modes, archived decisions
