# Package scanning for bulk self-binding

Status: proposed concept, deferred. Scope is narrow: it applies only to strict mode. No implementation exists; treat any names here as descriptive placeholders, not committed API.

Related decisions:
- [Implicit Creation Policy](./implicit_creation_policy.md): read first — its package-level allow rules give permissive and semi-strict modes on-demand implicit self-binding, so this scanning concept applies only where that policy does not: strict mode.
- [Strict Mode](./strict_mode.md): read for the one mode where implicit self-binding is off, so bulk explicit registration is the only way to avoid per-class `bind()` calls.
- [bind(...) API](./bind_api.md): read for `bind_many(...)`, the existing manual bulk-registration primitive this concept would automate.
- [Binding modules](./binding_modules.md): read for `BindingBox`, the module unit any scanning helper would populate.
- [Diagnostics and Introspection](./diagnostics.md): read for module-level cycle detection, which benefits from the clean type-to-package mapping scanning produces.

## 1. Problem

Strict mode disables implicit self-binding, so every managed type must be explicitly
registered. An application that wants strict-mode ownership and fail-fast resolution but owns
dozens of concrete service classes must list each one in `bind()`/`bind_many(...)` and keep
that list in sync by hand as classes are added and removed. The registration carries no
information beyond "this concrete class exists and lives in this package," yet a missed entry
is a silent gap in the managed graph.

Permissive and semi-strict modes do not have this problem: `allow_package("my_app")` in the
implicit creation policy makes every unbound concrete type under a package eligible for
implicit self-binding on demand, lazily and without enumeration. Strict mode never consults
that policy, so it has no equivalent relief. This concept exists only to close that strict-mode
gap.

## 2. Concept: derive self-binds from package membership

Scan a package and emit an explicit self-bind for each owned concrete class, so package
membership drives registration instead of a hand-maintained list. The output is ordinary
explicit self-binds — the same effect as calling `bind(ServiceClass)` for each discovered
class — so it stays fully compatible with strict mode's contract that only declared bindings
resolve.

Selection stays a coarse package filter; it does not classify types by construction style.
Excluding dataclasses, applying constructor-shape guards, or treating declarative classes as
non-services are policy concerns that belong to the implicit creation policy as explicit
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
need explicit `bind(Interface, Implementation)`. So even with scanning, a strict-mode composition
root keeps an explicit section for its abstract bindings, and scanning only removes the
mechanical self-bind list.

Selection should be explicit rather than heuristic. If scanning is pursued, exclusions belong
to the caller (name a type to skip, or supply a predicate), not to built-in guesses about which
classes are "services." This keeps the mechanism aligned with implicit creation policy: package
membership is a coarse selector, and anything finer is an explicit user rule.

## 5. Open questions

- Is the strict-mode bulk-registration pain real enough to justify a scanning mechanism, or is
  a maintained `bind_many(...)` list an acceptable and more explicit cost?
- Could the same relief come from a smaller feature — for example, a helper that lists concrete
  classes in already-imported modules for the caller to pass to `bind_many(...)` — keeping
  discovery explicit and avoiding import-time side effects entirely?
- If adopted, what module name and grouping would the scanned bindings carry, and how does that
  feed the type-to-package mapping module-level cycle detection wants?
