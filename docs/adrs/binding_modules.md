# Binding modules

## Problem

As a project grows, dependency bindings accumulate. Without organisation they end up
in one large setup block that is hard to navigate, impossible to reuse across
environments or test configurations, and gives no signal about which bindings belong
to which feature.

The goal is a lightweight grouping mechanism that:
- has zero ceremony for simple apps (no new concepts introduced),
- scales naturally to large apps with many features and multiple environments,
- preserves the existing `bind()` API unchanged,
- gives diagnosability payoff: errors can say *which module* a binding came from.

## Existing primitive: `BindingBox`

`BindingBox` is already the binding registry. `DIBox` is a `BindingBox` that also owns
resolved instances. A binding module is simply a standalone `BindingBox` — a collection
of binding rules that lives independently of any active container.

The implementation is then minimal: `DIBox` holds a list of addon `BindingBox` instances
and searches them during resolution in order.

```python
box.add_bindings(binding_box)    # proposed API — adds BindingBox to the search chain
```

`BindingBox` instances are cheap to create, hold no state beyond their rules, and can
be constructed at import time without caring whether a container exists yet.

## Defining a module

A module is a module-level `BindingBox` in the file that owns that feature's code.
No base class, no decorator, no registration ceremony.

```python
# billing/deps.py
from dibox import BindingBox

bindings = BindingBox()
bindings.bind(PaymentGateway, StripeGateway)
bindings.bind(InvoiceStorage, S3InvoiceStorage)
bindings.bind(BillingService)
```

```python
# notifications/deps.py
from dibox import BindingBox

bindings = BindingBox()
bindings.bind(EmailSender, SendGridSender)
bindings.bind(NotificationService)
```

```python
# main.py
from billing.deps import bindings as billing_bindings
from notifications.deps import bindings as notification_bindings

async with DIBox() as box:
    box.add_bindings(billing_bindings)
    box.add_bindings(notification_bindings)
```

The `BindingBox` objects are defined once and reused. `add_bindings` is a constant-time
operation — it appends to a list, no iteration over the bindings themselves.

## Parameterised modules

When a module needs runtime configuration (environment-specific URLs, feature flags,
credentials), a factory function produces the `BindingBox`:

```python
# storage/deps.py
def s3_bindings(bucket: str, region: str) -> BindingBox:
    box = BindingBox()
    box.bind(StorageConfig, instance=StorageConfig(bucket=bucket, region=region))
    box.bind(StorageClient, S3StorageClient)
    return box

def local_bindings(base_path: Path) -> BindingBox:
    box = BindingBox()
    box.bind(StorageConfig, instance=StorageConfig(base_path=base_path))
    box.bind(StorageClient, LocalStorageClient)
    return box
```

```python
# main.py
storage = s3_bindings(bucket="prod-assets", region="eu-west-1") if is_prod else local_bindings(Path("/tmp"))

async with DIBox() as box:
    box.add_bindings(storage)
    box.add_bindings(billing_bindings)
```

This is the standard pattern for environment switching or A/B feature toggles — no
special API needed.

## Scoped modules

Binding modules pair well with container nesting (see `scopes.md`). A module can define
the bindings for a specific scope lifetime without knowing or caring about the
parent container:

```python
# pipeline/gpu_stage.py — reusable recipe for any GPU-accelerated stage
gpu_stage_bindings = BindingBox()
gpu_stage_bindings.bind(GPUContext)
gpu_stage_bindings.bind(StageBuffer)

enhance_bindings = BindingBox()
enhance_bindings.bind(Enhancer)

classify_bindings = BindingBox()
classify_bindings.bind(Classifier)
```

```python
async with DIBox(parent=run) as stage:
    stage.add_bindings(gpu_stage_bindings)   # shared hardware setup
    stage.add_bindings(enhance_bindings)     # stage-specific services
    stage.bind(StageContext, instance=StageContext("enhance", tmp_dir))
    tiles = await stage.call(run_enhance, tiles=tiles)
```

The driver decides *when* to enter a scope; the module defines *what* is available
inside it. These concerns stay separate.

## Diagnostics: tracing bindings back to their module

Once `DIBox` holds a list of named `BindingBox` addons, every binding lookup can report
which module it came from. This converts opaque errors into actionable ones:

```
KeyError: No binding found for PaymentGateway
  searched: [app container, billing.deps, notifications.deps]
  hint: PaymentGateway was found in billing.deps but no implementation is bound
```

To make these messages useful, the module needs an identity. Two options:

**Option A: automatic — use `__name__` of the binding box's defining module**

Inspect the call site when `BindingBox()` is constructed and capture the module path.
Zero extra API. Works for the common case of module-level `bindings = BindingBox()`.
Fragile for programmatically constructed boxes.

**Option B: explicit label**

```python
bindings = BindingBox(name="billing")
```

One optional argument, easy to add later, unambiguous. Unlocks cleaner error messages
and could surface in `validate()` / `visualize()` output ("billing → PaymentGateway →
StripeGateway").

Option B is the right default to design toward; Option A can be a convenience on top.

## Testing: swapping modules

The same pattern that enables environment switching enables test overrides without
subclassing or monkey-patching:

```python
mock_billing = BindingBox()
mock_billing.bind(PaymentGateway, MockGateway)
mock_billing.bind(InvoiceStorage, InMemoryInvoiceStorage)

async with DIBox() as box:
    box.add_bindings(notification_bindings)   # real notifications — base layer
    box.add_bindings(mock_billing)            # override layer — registered last, wins
```

Resolution order: **last-registered wins** among addons. A module registered later
overrides any earlier module that binds the same type. The container's own direct
bindings (`box.bind(...)`) always take highest precedence regardless of order — they
are the most explicit signal.

This matches the convention used by .NET DI, Spring, and Dishka, and reads naturally:
register the base layer first, add specialisations or overrides on top. Guice's
first-wins approach is the notable outlier — and the need for its explicit
`Modules.override()` escape hatch is the practical argument against it.

## What this does not need

- A `Module` base class. `BindingBox` is already the right abstraction.
- A `scan()` or auto-discovery mechanism. Import and `add_bindings()` is two explicit
  lines; scanning adds magic with no DX benefit for the common case.
- Namespacing of type selectors. Bindings are still keyed by type — modules are a
  *grouping and diagnostics* concept, not a type system extension.

## Future: module-level cycle detection

There are two distinct levels at which circular dependencies can appear:

**Type-level cycles** are caught during resolution — `BillingService → InvoiceService → BillingService`.
These are runtime errors, covered in `greedy_resolution.md`.

**Module-level cycles** are a structural design smell that doesn't necessarily produce
a type-level cycle:

```
billing.BillingService    depends on  notifications.NotificationClient
notifications.EventLogger depends on  billing.BillingConfig
```

No type cycle exists. Both resolve fine. But `billing` and `notifications` are
mutually dependent at the module level — a tight coupling that makes either module
impossible to reuse, test, or version independently. In a large codebase this kind of
entanglement is invisible without tooling.

### Why it's only detectable with named modules

Module-level cycle detection requires knowing *which module owns which type*. That
information only exists once `BindingBox` instances have names and are registered with
`add_bindings()`. A flat container with no modules has no concept of module membership.

This is one concrete reason to give `BindingBox` a `name=` parameter beyond just
improving error messages.

### How detection would work

1. After all modules are registered, `box.validate()` builds a **type-to-module** map:
   for every type bound in a named `BindingBox`, record its owning module.
2. For each module, for each bound type, inspect that type's factory/constructor
   signature to find its dependencies.
3. For each dependency, look up its owning module in the map from step 1.
4. Construct a directed **module dependency graph**: an edge `A → B` means some type
   in module A depends on some type owned by module B.
5. Run cycle detection (standard DFS) on the module graph.
6. Report any cycles with the specific cross-module edges that form them:

```
Warning: module-level cycle detected
  billing → notifications: BillingService depends on NotificationClient
  notifications → billing: EventLogger depends on BillingConfig
  consider extracting shared types into a third module (e.g. "shared" or "core")
```

### Open questions before implementing

- **Types with no module**: auto-wired types and types bound directly on the container
  (not via any `BindingBox`). They could be assigned to an implicit `"(app)"` module, or
  excluded from module-graph analysis entirely.
- **Severity**: should this be an error or a warning? A module cycle doesn't break
  resolution, so a warning with opt-in strict mode seems more appropriate.
- **When to run**: `validate()` is the natural place. Adding it to `__aenter__` silently
  on every container entry would be too expensive and too opinionated.
- **Partial graphs**: if only some modules are named, the cycle analysis covers only
  the named subset. This is probably acceptable — partial analysis is better than none.

### Usefulness vs. cost

The analysis is cheap (graph construction is O(bindings × deps), cycle detection is
O(modules + edges)), but understanding the output requires developers to think about
module boundaries consciously. The feature is most valuable in larger codebases where
module coupling is invisible without tooling, and least valuable in small apps where
everything is in one or two modules anyway. Worth building as part of `validate()` once
named modules are in place, but not a blocker for the initial module implementation.

## Future: package-aware auto-binding

See [package_binding.md](package_binding.md) for the full proposal.

The core idea: a `PackageBindingBox` that scans a Python package and auto-binds all
service classes it finds, eliminating the per-class `bind()` boilerplate. Class
ownership is determined by `cls.__module__`, which also makes this the most accurate
input for module-level cycle detection.
