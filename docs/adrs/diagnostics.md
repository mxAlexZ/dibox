# Diagnostics and Introspection

Status: partially implemented.

Resolution stack errors exist in source through `ResolutionError`. Cycle detection,
`validate()`, `graph()`, and module-aware diagnostics remain proposed.

Related ADRs:

- [strict_mode.md](strict_mode.md): explicit-binding mode makes validation coverage more complete.
- [implicit_self_binding.md](implicit_self_binding.md): permissive fallback limits what diagnostics can know before runtime.
- [entrypoints.md](entrypoints.md): entry points determine which resolution roots diagnostics can traverse.
- [binding_modules.md](binding_modules.md): binding modules provide future ownership metadata for module-aware diagnostics.

## Resolution stack errors

A common DI failure points at a low-level dependency while hiding the high-level request
that caused it. DIBox tracks a resolution stack during `provide()` and includes it in
`ResolutionError` messages.

Example failure shape:

```
Can't resolve (db_url: str).
Reason: requested type is not a concrete class.
Resolution path:
- db_url: str  <-- failure
- AppConfig
- StorageClient
```

The important property is not the exact wording; it is that errors preserve the path
from the requested root to the failing dependency.

## Type-level cycle detection

Type-level cycles are runtime resolution errors: `ServiceA` depends on `ServiceB`, and
`ServiceB` depends on `ServiceA`. Source currently tracks the stack but does not check
whether the next frame already exists in it, so explicit cycle detection is still a
follow-up.

The intended behavior is to fail before recursion overflows and report the repeated
frame:

```
Circular dependency detected.
Resolution path:
- ServiceA  <-- cycle
- ServiceB
- ServiceA
```

## Proactive validation APIs

`box.validate()` should verify container configuration without fully instantiating every
object. It traverses registered factories and constructors, reporting missing bindings,
unconstructable dependencies, and cycles.

`box.graph()` should expose the same dependency graph for visualization, debugging, or
tooling. A simple structured representation is enough; Graphviz or Mermaid output can be
adapters rather than core API.

Resolution mode affects coverage:

- Strict: the managed type set is known from explicit bindings, so validation and graph
  output can be comprehensive.
- Semi-strict: explicit roots are known, but transitive implicit nodes may be derived by
  following type hints from those roots.
- Permissive: the resolvable type set is open-ended, so validation needs explicit roots,
  such as `box.validate(from_entrypoints=[WebApp, Cli])`.

## Module-aware diagnostics

Binding modules make ownership visible if modules have identities. A future
`BindingBox(name=...)` should feed diagnostics with source information such as:

- which module supplied the selected binding,
- which modules were searched for a missing binding,
- which module owns each node in `validate()` and `graph()` output.

Explicit names are preferable to call-site inspection. Automatic names based on the
defining Python module can be a convenience later, but they are fragile for factory-made
or programmatically composed boxes.

## Module-level dependency cycles

Module-level cycles are structural coupling problems, not necessarily type-level cycles:

```
billing.BillingService    depends on notifications.NotificationClient
notifications.EventLogger depends on billing.BillingConfig
```

Both objects may resolve successfully, but `billing` and `notifications` are no longer
independently reusable. This belongs in `validate()` as a named-module analysis, not in
normal runtime resolution.

The algorithm is straightforward once named modules exist:

1. Build a type-to-module map for bindings in named `BindingBox` instances.
2. Inspect each bound type's factory or constructor dependencies.
3. Convert cross-module type dependencies into module graph edges.
4. Run cycle detection on the module graph.
5. Report the concrete type dependency behind each module edge.

This should probably be a warning by default. A module cycle does not break resolution;
it signals an architecture smell. Strict validation modes can later choose to promote it
to an error.

Open questions:

- Types with no module: direct container bindings and implicit self-bindings could be
  assigned to an implicit app module or excluded from module-graph analysis.
- Partial naming: if only some modules are named, the analysis should cover the named
  subset rather than requiring all modules to participate.
- Semi-strict introspection: derived transitive nodes can appear only in diagnostic
  output, or be materialized as generated bindings. Materialization improves graph
  completeness but adds implicit registry state.
