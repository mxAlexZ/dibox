# DIBox Design Review Split Index

Documentation for giving LLMs and humans a clear context of the design decisions, trade-offs, and open questions.

The documents can contain unpolished ideas. It is not part of the public documentation.

See [adr_concept.md](adr_concept.md) for ADR purpose and lifecycle; see repository instructions for retrieval and update workflow.

## Meta
ADRs that define the ecosystem and guiding principles. Read first when onboarding or before writing new ADRs.
 - [adr_concept.md](adr_concept.md): why ADRs exist, information economics, delivery leverage, lifecycle stages, and why maintenance matters
 - [philosophy.md](philosophy.md): progressive disclosure of complexity — zero-config defaults with explicit advanced controls
 - [ideas.md](ideas.md): active roadmap (testing override API, startup initialization), deferred proposals (resolver args, non-destructive signature mode, per-call strict), archived decisions

## Binding
How dependencies are declared, registered, and organized into modules.
 - [bind_api.md](bind_api.md): `bind(...)` argument forms, `bind_many`, generator/contextmanager factory support, rejected fluent APIs
 - [binding_modules.md](binding_modules.md): `BindingBox` as standalone binding collection, `add_bindings`, last-registered-wins precedence, parameterized and scoped modules, named-module diagnostics, future module-level cycle detection
 - [package_binding.md](package_binding.md): `PackageBindingBox` package scanning, auto-self-binding filters, dataclass exclusion, lazy import caveats, cycle detection integration
 - [named_bindings.md](named_bindings.md): argument-name matching as default, `Annotated` + `Named`/`Token` as explicit override, `NewType` alternative, third-party integration pattern

## Resolution & Runtime
How the container resolves dependencies, manages instance lifetimes, and exposes injection entrypoints.
 - [implicit_self_binding.md](implicit_self_binding.md): permissive implicit self-binding, confusion with auto-wiring, zero-dependency guard proposal, and limits of convenience-first resolution
 - [strict_mode.md](strict_mode.md): strict-mode explicit-binding contract, fail-fast semantics, migration path from permissive defaults
 - [entrypoints.md](entrypoints.md): `@inject` + contextvar container resolution, `Injected[T]` + signature rewriting, `container.call()`/`partial()`, `Injector`, mode-dependent behavior
 - [semi_strict_mode.md](semi_strict_mode.md): implemented middle mode (explicit roots + implicit transitive expansion), with open introspection-surface questions and optional safety-filter follow-ups
 - [scopes.md](scopes.md): `DIBox(parent=...)` nesting as scope primitive, instance ownership/shadowing rules, contextvar-based `@inject` for framework integration, why `scope=` on `bind()` was rejected
 - [scopes_sketch.py](scopes_sketch.py): pipeline/Ray scope scenarios, app-run-stage nesting, `container.call()`, module reuse
 - [factories.md](factories.md): proposal for call-time factory args and container-aware factories for dynamic/context-driven dependency creation
 - [sync_async.md](sync_async.md): sync mode current limitation (`get()` only), proposed `provide_sync()` and sync factory behavior

## Developer Experience
Tools for debugging, validation, and observability.
 - [diagnostics.md](diagnostics.md): resolution stack errors, cycle detection, `validate()`/`graph()` for proactive validation, strict vs. permissive impact on diagnostics coverage
