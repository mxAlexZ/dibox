# Dependency Graphs as Compiled Binding Contexts

Status: partially implemented

Related ADRs:
- [diagnostics.md](diagnostics.md): `validate()` and `graph()` are the primary consumer APIs this design enables
- [scopes.md](scopes.md): scope boundaries are the natural candidate for graph reuse boundaries if sharing is ever introduced
- [implicit_self_binding.md](implicit_self_binding.md): defines the constructor-derived binding mechanism used when lookup finds no explicit binding
- [missing_binding_policy.md](missing_binding_policy.md): authorizes missing bindings at root and transitive positions, including the known cached-boundary limitation
- [entrypoints.md](entrypoints.md): `container.call()` needs dependency traversal as a dry-run probe to know which arguments are resolvable

## Motivation

`DIBox` coordinates binding registration, instance lifecycle, and dependency resolution — concerns with different owners and change rates. Resolution logic (binding lookup, signature introspection, dependency traversal, and missing-binding policy evaluation) accumulates in a flat container class, making `DIBox` harder to reason about and test in isolation.

`DependencyGraph` extracts resolution into a dedicated owner, it answers what can be resolved, which binding satisfies a slot, and what each binding depends on — without creating instances or starting context managers. This keeps `DIBox` as a thin hub and enables dry-run probes like `call()` and `validate()`.

## Current design

`DependencyGraph` is a resolution cache owned by `DIBox`. For a requested dependency, it derives binding metadata and required dependency slots once, then reuses that result on later traversals. This avoids repeating binding lookups and signature introspection when the same subtree appears under multiple roots.

Resolution runs in two stages: graph building compiles and caches dependency structure for a request, and graph walking traverses that compiled structure in dependency order while skipping already materialized branches. This keeps resolution pure and reusable, keeps instance creation in a separate side-effecting stage, and preserves diagnostics context (matched binding, implicit vs explicit resolution, and required dependency slots).

On an uncached miss, graph construction identifies whether the request is a root or transitive dependency and asks the missing-binding policy whether an implicit self-binding is authorized. Cached request boundaries do not yet preserve that authorization context; the policy ADR owns this known order-independence limitation.

## Future work

Two traversal behaviors are planned over the same resolution rules. Fail-fast should stop at the first missing or unbindable dependency (for provisioning and resolvability probes), while collect-all should continue and return a complete error set (for validation and graph inspection).

Graph sharing remains exploratory. Runtime already reuses materialised instances aggressively, so sharing resolution metadata is not automatically the highest-value optimization. The main open design question is composition ergonomics across scopes, so concrete sharing mechanics are deferred until scope boundaries and ownership rules are defined more explicitly.

## Open questions
- Should graph reuse be a public concept at all, or remain an internal optimization behind container/scope composition APIs?
- Which boundary should own reuse semantics: parent-container inheritance, reusable container templates, or another composition primitive?
