
---

# Issue 1 (umbrella): Generalize the resolution context

### Problem

Bindings are currently matched on `(type, arg_name)`. To customize a **single** injection point, there are two workarounds and both have costs:

1. **Bind globally, narrow by arg name.** The binding still applies to every consumer that happens to use that parameter name. Name collisions are avoided by convention, not by construction.

2. **Write a factory for the consumer.** The factory must then enumerate *all* of the consumer's dependencies just to pass one value through:

```python
@service
class Dashboard:
    def __init__(self, page: Page, widgets: list[Widget], logger: Logger, clock: Clock): ...

def build_dashboard(logger: Logger, clock: Clock) -> Dashboard:  # must list everything
    return Dashboard(page, my_widgets, logger, clock)

dibox.bind(Dashboard, build_dashboard)
```

Adding a fifth dependency to `Dashboard` breaks the factory, even though the factory only exists to supply `page` and `widgets`. The pass-through boilerplate grows with the consumer's dependency count.

### Direction

Treat `arg_name` as one dimension of a more general **resolution context**, and let bindings declare which contexts they apply to. Three follow-ups:

- **#2 — `when(...)` binding conditions**: express *where* a binding applies.
- **#3 — Context-keyed instance cache**: `(type, arg_name)` → `(type, context)`.
- **#4 — `explain()`**: make contextual resolution inspectable.

Notably, `resolution_stack` is already threaded through graph traversal for error messages, so consumer identity is available at match time and simply isn't part of the match key today.

Prerequisite for all three: promote resolution context to a first-class, public, hashable object rather than an incidental tuple.

---

# Issue 2: `when(...)` conditions on bindings

### Proposal

Let `bind()` accept a condition describing which injection points it applies to:

```python
dibox.bind(Page, page, when=injected_into(Dashboard))
dibox.bind(list[Widget], build_widgets, when=arg_named("widgets"))
dibox.bind(Config, dev_config, when=injected_into(Dashboard) & arg_named("config"))
```

`bind(Type, "arg_name", target)` becomes sugar for `when=arg_named(...)`, so existing code is unaffected.

This removes the pass-through factory from the umbrella issue entirely — `Dashboard` resolves normally and gains new dependencies without touching any binding.

### Open questions

- **Surface**: keyword-only `when=` taking composable condition objects, vs a `When(injected_into=..., arg_name=...)` dataclass of optional criteria, vs a fluent `.when(...)` builder.
- **Composition**: support `&` / `|` / `~`, or keep conditions flat and non-composable initially?
- **Scope of `injected_into`**: immediate consumer only, or any ancestor in the resolution path? The latter enables "everything under X" but makes matching a path-matching problem.
- **Specificity ordering**: the current 3-tier fallback (`(type, name)` → `(type, ANY_ARG)` → `(ANY_TYPE, name)`) is a total order. Arbitrary conditions are not. Do we need explicit priority, a defined specificity ranking, or an ambiguity error when two conditions both match?
- **User-defined conditions**: allow `when=lambda ctx: ...`? Powerful, but caching requires conditions to be hashable and comparable (see #3).

### Alternatives considered

- Per-binding argument overrides: `bind(Dashboard, args={"widgets": build_widgets})`. Solves the boilerplate but uses string keys and describes the *consumer* rather than the dependency.
- Child/scoped containers: overrides by construction instead of declaration. Overlaps heavily — worth deciding whether both should exist.

---

# Issue 3: Key the instance cache on context, not arg name

### Problem

Instances are cached as `(requested_type, name)`. If bindings gain richer conditions (#2), a contextual binding can produce a different instance for a key the cache considers identical.

### Proposal

Generalize the cache key to `(type, context)`. The critical rule:

> **The cache key is derived from the context the winning binding matched on — not from the context of the request.**

```
resolve(type, context):
    binding, matched = bindings.find_match(type, context)
    cache_key = (type, matched.context)   # not (type, context)
```

Consequences:

- A global binding wins for every consumer → all requests collapse to one cache entry. Singleton semantics are unchanged.
- A contextual binding wins → the key includes that binding's condition, so it gets its own instance.

This makes *"singleton unless you deliberately scoped it"* a property the implementation guarantees, rather than a convention users must avoid violating. It also means the cache does not fragment just because a type has many consumers.

Worth doing on its own merits — the current key is a special case of this one.

### Open questions

- Conditions must be hashable with meaningful equality. Does that rule out `lambda`-based conditions, or do they get identity semantics?
- Should two structurally-distinct conditions that always match the same set ever share an entry? (Proposed: no — don't attempt normalization.)
- Interaction with disposal ordering, which is currently LIFO over the instance list.

---

# Issue 4: `explain()` for resolution diagnostics

### Problem

When resolution produces an unexpected instance, there's no way to ask *why*. `ResolutionError` reports the path on failure, but successful-yet-wrong resolutions are silent. Richer matching rules (#2) increase how often this matters.

### Proposal

```python
print(dibox.explain(Dashboard))
```

```
Dashboard  <- self-binding
├─ page: Page          <- instance, when injected_into(Dashboard)   [cache: (Page, injected_into(Dashboard))]
├─ widgets: list[Widget] <- factory build_widgets, when arg_named('widgets')
├─ logger: Logger      <- self-binding                              [cache: (Logger, ANY_ARG)]
└─ clock: Clock        <- UNRESOLVED: no matching binding
```

Shows, per node: the winning binding, the condition it matched on, and the resulting cache key.

The graph walk already exists; this reuses it without instantiating. That also yields a cheap `dibox.validate()` for fail-fast startup checks on missing or ambiguous bindings.

### Open questions

- Static (bindings only) vs live (reflects the current instance cache) — or both, via a flag?
- Return a structured object with a `__str__`, rather than a string, so it's usable in tests.
- Should ambiguous matches be surfaced here as warnings?

---

Two things that will help these survive review: file #3 as independently valuable (it's a correctness improvement to the existing key, not just scaffolding for #2), and expect the specificity-ordering question in #2 to attract the most debate — having a concrete proposed ranking ready will move it along faster than leaving it open.