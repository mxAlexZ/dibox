# Package-aware auto-binding

See also: [binding_modules.md](binding_modules.md), [greedy_resolution.md](greedy_resolution.md)

## The boilerplate problem

Adding a new service class today involves four steps:

1. Write `class BillingService` in `billing/services.py`
2. Re-export from `billing/__init__.py`
3. Add to `__all__`
4. `bindings.bind(BillingService)` in `deps.py`

Steps 2–4 carry no information: the class exists, it lives in the billing package,
that's the entire intent. They exist only because the container doesn't know where to
look.

## The idea: `PackageBindingBox`

A `BindingBox` subclass (or factory) that scans a Python package and auto-binds all
service classes it finds there. The module name resolves automatically from the package.

```python
# billing/deps.py — the entire file
from dibox import PackageBindingBox
from billing import services, payment, storage  # imports trigger discovery

bindings = PackageBindingBox(package="billing")
# name="billing" is inferred; all service classes auto-bound
```

Steps 2–4 collapse to zero. The developer writes a class, imports the submodule (which
they likely already do), and the container picks it up.

## Auto-binding criteria

Not everything in a package is a service. The scan applies filters in order:

- **Concrete class**: exclude ABCs, Protocols, Enums — none of these should be
  constructed by the container.
- **Package ownership**: `cls.__module__.startswith(package_name)`. Filters out
  third-party classes re-exported through the package (`from stripe import Gateway`
  stays out; `stripe.__module__` is `"stripe.client"`, not `"billing"`).
- **Dataclass exclusion**: `dataclasses.is_dataclass(cls)` — dataclasses are DTOs and
  value objects, not services. Excluded by default with an opt-in to override.
- **Zero-dep guard** (from `greedy_resolution.md`): skip any type where
  `inspect.signature` shows no required parameters. These are value types —
  `Path()`, config objects with all-default fields. The same guard that protects
  `provide()` from silently constructing primitives protects package scanning from
  binding those types.
- **Public classes only**: skip names starting with `_`.

What remains after filtering is almost always exactly "the service classes."

## What auto-binding can and cannot do

Auto-binding can only produce **self-binds**: `bind(BillingService)` — requesting
`BillingService` constructs `BillingService`. It cannot know that `PaymentGateway`
should resolve to `StripeGateway`. Abstract types and interface-to-implementation
mappings still need explicit `bind()` calls in the same box.

```python
# billing/deps.py
bindings = PackageBindingBox(package="billing")
bindings.bind(PaymentGateway, StripeGateway)   # explicit — auto-bind can't infer this
```

## Discovery timing

`PackageBindingBox` can only see classes that are already imported at the moment it is
constructed. If `billing` lazily imports its submodules (very common), those classes
won't be visible yet.

**Option A: caller imports submodules first (recommended default)**
```python
from billing import services, payment   # explicit — developer controls what's scanned
bindings = PackageBindingBox(package="billing")
```
Simple, predictable, no magic. The imports are usually already present in well-organised
packages.

**Option B: eager scan via `pkgutil.walk_packages` (opt-in)**
```python
bindings = PackageBindingBox(package="billing", scan_all=True)
```
The box imports all submodules itself during construction. Zero-setup for the caller,
but has side effects: all submodule code runs at `BindingBox` construction time, which
may be surprising and makes import errors harder to attribute.

## The DTO / dataclass false-positive problem

`@dataclass class Invoice(items: list[LineItem], total: Decimal)` lives in the billing
package, is concrete, has required fields — it passes all filters except the dataclass
exclusion. Without that check, requesting `Invoice` would trigger an attempt to resolve
`list[LineItem]` and `Decimal`, both of which would fail or produce nonsense.

The dataclass exclusion is the primary guard. Additional mitigations:
- `_` prefix convention — `_Invoice` is skipped.
- Explicit exclusion: `bindings.exclude(Invoice)`.
- Accept that it fails loudly at `validate()` or first `provide()` rather than
  silently, so the developer gets a clear error pointing at the misconfigured type.

The zero-dep guard already catches the simpler case: `@dataclass class Config` with
all-default fields is skipped by it. Required-field dataclasses are the residual gap
that the dataclass check closes.

## Caveats summary

| Issue | Impact | Mitigation |
|---|---|---|
| Lazy submodule imports | Classes missed at scan time | Import submodules before constructing the box (Option A) |
| Dataclasses with required fields | Auto-bound but unresolvable | Exclude `dataclasses.is_dataclass()` by default |
| Abstract types need explicit bind | No change from today | Explicit `bind()` in the same box |
| pyright can't verify auto-bound types | No static error if type is unresolvable | `provide(BillingService)` is still typed; auto-binding is a resolution convenience, not a type system extension |

## Relationship to module-level cycle detection

`PackageBindingBox` provides the most natural `name=` value and the tightest
type-to-module mapping possible: `cls.__module__` directly encodes package membership
with no heuristics. This makes it the ideal input for the module-level cycle detection
described in `binding_modules.md`: no ambiguity about which module a type belongs to,
no manual attribution needed.
