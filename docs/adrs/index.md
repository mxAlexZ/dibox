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
 - [bind_api.md](bind_api.md): `bind(...)` argument forms, `bind_many`, generator/contextmanager factory support, rejected fluent APIs
 - [binding_modules.md](binding_modules.md): implemented `BindingBox` modules via `add_bindings`; composition-root grouping, module precedence
 - [package_binding.md](package_binding.md): deferred concept for scanning a package to emit bulk explicit self-binds; scoped to strict mode only, since implicit creation policy `allow_package` already covers permissive/semi-strict; key tension is discovery timing (lazy imports vs eager-scan import side effects)
 - [named_bindings.md](named_bindings.md): argument-name matching as default, `Annotated` + `Named`/`Token` as explicit override, `NewType` alternative, third-party integration pattern

## Resolution & Runtime
How the container resolves dependencies, manages instance lifetimes, and exposes injection entrypoints.
 - [implicit_self_binding.md](implicit_self_binding.md): implicit self-binding as shared permissive/semi-strict mechanism for zero-config concrete graph internals; permissive onboarding defaults, semi-strict root-boundary mitigation, open-graph risks
 - [implicit_creation_policy.md](implicit_creation_policy.md): implicit self-binding eligibility for unbound concrete types in permissive/semi-strict resolution; allow and deny rules match packages, exact types, or arbitrary predicates, with deny precedence; fallback guards handle unruled types: `"value-types"` defaults to blocking known values, `"zero-dependency"` blocks zero-arg constructors, and `"deny-all"` creates strict allowlists
 - [zero_dependency_guard.md](zero_dependency_guard.md): earlier proposed hard-coded guard for zero-required-arg leaf types; predecessor context for implicit creation policy
 - [strict_mode.md](strict_mode.md): strict-mode explicit-binding contract, fail-fast semantics, migration path from permissive defaults
 - [entrypoints.md](entrypoints.md): `@inject` + contextvar container resolution, `Injected[T]` + signature rewriting, `container.call()`/`partial()`, `Injector`, mode-dependent behavior
 - [semi_strict_mode.md](semi_strict_mode.md): implemented middle mode (explicit roots + implicit transitive expansion), with open introspection-surface questions and optional safety-filter follow-ups
 - [scopes.md](scopes.md): `DIBox(parent=...)` nesting as scope primitive, instance ownership/shadowing rules, binding modules inside scopes, contextvar-based `@inject`, why `scope=` on `bind()` was rejected
 - [scopes_sketch.py](scopes_sketch.py): pipeline/Ray scope scenarios, app-run-stage nesting, `container.call()`, module reuse
 - [factories.md](factories.md): proposal for call-time factory args and container-aware factories for dynamic/context-driven dependency creation
 - [sync_async.md](sync_async.md): sync mode current limitation (`get()` only), proposed `provide_sync()` and sync factory behavior

## Developer Experience
Tools for debugging, validation, and observability.
 - [diagnostics.md](diagnostics.md): implemented resolution stack errors, proposed cycle detection, `validate()`/`graph()`, module-aware diagnostics, module-level dependency cycles
 - [dependency_graph.md](dependency_graph.md): separation of resolution logic from `DIBox` hub; `DependencyGraph` owns binding lookup, signature introspection, traversal, and mode enforcement; `BindingLookup` protocol; sync-resolution vs async-materialisation split; planned dual traversal behaviors (fail-fast vs collect-all); deferred graph sharing across scope boundaries
