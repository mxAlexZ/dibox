# Binding modules

Status: implemented.

## Motivation

Bindings need an organization boundary before they need a framework. Small apps can
keep using `DIBox.bind()` directly; larger apps need to group bindings by feature,
environment, entry point, or test fixture without introducing a second registration API.

Direct binding stays the default path, and module composition appears only when the binding set is large enough to need names and seams.

## Decision details

A binding module is a standalone `BindingBox` added to a container with
`DIBox.add_bindings()`.

`BindingBox` stores binding rules only. `DIBox` owns resolved instances, lifecycle, and
resolution. That split keeps modules cheap to create, safe to import, and reusable across
entry points.

This keeps the same `bind()` API everywhere, lets modules be created at import time, and
keeps final composition explicit at the application boundary.

Resolution searches binding rules in this order:

1. direct bindings on the `DIBox` instance,
2. added modules in reverse registration order,
3. implicit self-binding when the missing-binding policy authorizes it.

Direct container bindings are the most explicit composition-root signal and always win.
Among modules, last-registered wins. This makes layered composition possible without
special APIs: register broad modules first, then narrower environment or entry-point
modules if they intentionally replace the same binding.

## DX impact

- Simple apps pay no cost: no module concept is required until bindings need grouping.
- Feature bindings can live next to feature code, while the composition root remains the
  one place that decides which modules participate.

## Boundaries

Binding modules group binding rules only. They do not change selector semantics, create
namespaces, own instances, or define lifetimes.

Rejected for the core concept:

- `Module` base class, decorators, or installer classes.
- Automatic discovery or package scanning in `add_bindings()`.
- Namespacing type selectors by module.

Non-critical follow-ups are optional module names for diagnostics, package-aware
auto-binding helpers, and module-aware `validate()` / `graph()` output.

## Related ADRs

- [diagnostics.md](diagnostics.md): owns binding-source attribution, `validate()` / `graph()`, and future module-level dependency analysis.
- [scopes.md](scopes.md): owns lifetime boundaries; binding modules can be added inside a scope but do not define the scope.
- [package_binding.md](package_binding.md): owns package scanning and auto-self-binding as a convenience for building `BindingBox` instances.
