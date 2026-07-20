# DIBox Design Review Split Index

Documentation for giving LLMs and humans a clear context of the design decisions, trade-offs, and open questions.

The documents can contain unpolished ideas. It is not part of the public documentation.

See [adr_concept.md](adr_concept.md) for ADR purpose and lifecycle; see repository instructions for retrieval and update workflow.

## Meta
ADRs that define the ecosystem and guiding principles. Read first when onboarding or before writing new ADRs.
 - [adr_concept.md](adr_concept.md): why ADRs exist, information economics, delivery leverage, lifecycle stages, and why maintenance matters
 - [philosophy.md](philosophy.md): progressive disclosure of complexity — zero-config defaults with explicit advanced controls
 - [ideas.md](ideas.md): active roadmap (test module composition helpers, dependency graph introspection, startup initialization), deferred proposals (named binding modules, resolver args, non-destructive signature mode), archived decisions

## Binding
How dependencies are declared, registered, and organized into modules.
 - [bind_api.md](bind_api.md): `bind(...)` argument forms, explicit self-binds and roots, `bind_many`, generator/contextmanager factories, rejected fluent APIs
 - [binding_modules.md](binding_modules.md): implemented `BindingBox` modules via `add_bindings`; composition-root grouping, direct/module/implicit precedence, no instance or lifetime ownership
 - [package_binding.md](package_binding.md): deferred package scanning for enumerable explicit self-binds and package-wide root access; discovery completeness versus eager-import side effects
 - [named_bindings.md](named_bindings.md): argument-name matching as default, `Annotated` + `Named`/`Token` as explicit override, `NewType` alternative, third-party integration pattern

## Resolution & Runtime
How the container resolves dependencies, manages instance lifetimes, and exposes injection entrypoints.
 - [implicit_self_binding.md](implicit_self_binding.md): constructor-derived self-bindings for unbound concrete classes; recursive annotated dependencies, explicit-binding precedence, and limits of inferred recipes
 - [missing_binding_policy.md](missing_binding_policy.md): canonical missing-binding authorization; root/transitive defaults, `"open"`/`"explicit-roots"`/`"closed"` presets, type/package/predicate rules, cached-boundary limitation
 - [entrypoints.md](entrypoints.md): implemented `@inject`, `Injected[T]`, contextvar and fixed-container selection; proposed `call()`/`partial()` reuse policy root semantics per parameter
 - [scopes.md](scopes.md): `DIBox(parent=...)` nesting as scope primitive, instance ownership/shadowing rules, binding modules inside scopes, contextvar-based `@inject`, why `scope=` on `bind()` was rejected; open problem: placement of implicitly created instances (binding = recipe + ownership + placement, lifetime invariant, candidate rules incl. container-local lean, policy locality/inheritance)
 - [scopes_sketch.py](scopes_sketch.py): pipeline/Ray scope scenarios, app-run-stage nesting, `container.call()`, module reuse
 - [factories.md](factories.md): proposal for call-time factory args and container-aware factories for dynamic/context-driven dependency creation
 - [sync_async.md](sync_async.md): sync mode current limitation (`get()` only), proposed `provide_sync()` and sync factory behavior

## Developer Experience
Tools for debugging, validation, and observability.
 - [diagnostics.md](diagnostics.md): implemented resolution-path errors; proposed cycle detection, `validate()`/`graph()`, explicit/open/predicate root enumeration boundaries, module-aware diagnostics
 - [dependency_graph.md](dependency_graph.md): compiled binding context owned outside the `DIBox` hub; binding lookup, signature introspection, policy evaluation, cached traversal, fail-fast/collect-all plans, cached-root limitation
