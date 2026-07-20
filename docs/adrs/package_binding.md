# Package scanning for explicit self-bindings

Status: proposed concept, deferred. No implementation exists; treat any names here as descriptive placeholders, not committed API.

Related decisions:
- [Missing-Binding Policy](./missing_binding_policy.md): package allow rules authorize lazy transitive construction without creating explicit bindings; scanning serves a different need.
- [bind(...) API](./bind_api.md): read for `bind_many(...)`, the existing manual bulk-registration primitive this concept would automate.
- [Binding modules](./binding_modules.md): read for `BindingBox`, the module unit any scanning helper would populate.
- [Diagnostics and Introspection](./diagnostics.md): read for module-level cycle detection, which benefits from the clean type-to-package mapping scanning produces.

## 1. Problem

Package allow rules already solve low-boilerplate transitive wiring: matching concrete classes
can be constructed lazily without enumeration or explicit registration. Scanning is relevant
only when an application wants package membership to emit real bindings — for example, to make
every discovered class an explicit root or to expose a finite binding set to diagnostics and
module tooling.

Maintaining that set through `bind()` or `bind_many(...)` couples the composition root to every
class and can drift as a package changes. Deriving bindings from package membership removes the
hand-maintained list, but also makes every discovered class part of the explicit container
surface. That widening is justified only when the package itself is intended to be an ownership
boundary; it is not a general replacement for selective root declarations.

## 2. Concept: derive self-binds from package membership

Scan a package and emit an explicit self-bind for each owned concrete class, so package
membership drives registration instead of a hand-maintained list. The output is ordinary
explicit self-binds — the same effect as calling `bind(ServiceClass)` for each discovered
class. Each discovered class therefore bypasses missing-binding policy, can be requested as a
root, and becomes enumerable as binding metadata.

Selection stays a coarse package filter; it does not classify types by construction style.
Excluding dataclasses, applying constructor-shape guards, or treating declarative classes as
non-services are policy concerns that belong to the missing-binding policy as explicit
allow/deny rules, not to hardcoded scan heuristics. Baking such guesses into scanning would
duplicate that logic and contradict the policy's stance that construction style (dataclass,
attrs, plain class) is not a semantic category.

## 3. Key tension: discovery timing

The hard problem is not filtering; it is knowing which classes exist. A scan can only see
classes already imported when it runs. Packages that lazily import submodules — the common,
well-behaved case — expose nothing to scan at that moment.

Two ways to resolve it, both with real costs:

- Caller imports submodules first, then scans. Predictable and side-effect-free, but pushes
  the completeness burden back onto the developer: a forgotten import silently drops a class,
  reintroducing the very hand-sync drift scanning is meant to eliminate.
- The scan eagerly walks and imports the whole package. Zero caller setup, but runs all
  submodule import side effects at scan time and makes import errors harder to attribute to
  their source.

Neither is clean, and this tension is the main reason the concept stays deferred rather than
adopted. Eager scanning trades one maintenance hazard (forgotten bind calls) for another
(surprising import-time execution).

## 4. Scope limits

Scanning can only produce self-binds: requesting a concrete type constructs that same type.
It cannot infer interface-to-implementation mappings; abstract and protocol dependencies still
need explicit `bind(Interface, Implementation)`. Scanning only removes a mechanical concrete
self-bind list.

Selection should be explicit rather than heuristic. If scanning is pursued, exclusions belong
to the caller (name a type to skip, or supply a predicate), not to built-in guesses about which
classes are "services." This keeps the mechanism aligned with the missing-binding policy: package
membership is a coarse selector, and anything finer is an explicit user rule.

## 5. Open questions

- Is explicit package-wide root access or enumeration common enough to justify scanning, or is
  a maintained `bind_many(...)` list an acceptable and more deliberate cost?
- Could the same relief come from a smaller feature — for example, a helper that lists concrete
  classes in already-imported modules for the caller to pass to `bind_many(...)` — keeping
  discovery explicit and avoiding import-time side effects entirely?
- If adopted, what module name and grouping would the scanned bindings carry, and how does that
  feed the type-to-package mapping module-level cycle detection wants?
