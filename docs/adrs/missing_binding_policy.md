# Missing-Binding Policy

Status: implemented, with a known order-independence limitation at cached request boundaries.

Related documents:
- [Implicit Self-Binding](./implicit_self_binding.md): defines the construction mechanism authorized by this policy when no binding matches.
- [Dependency Graphs](./dependency_graph.md): owns binding lookup, graph compilation, caching, and policy integration.
- [Entrypoints](./entrypoints.md): owns the container surfaces that initiate root requests.
- [Diagnostics and Introspection](./diagnostics.md): uses explicit roots and policy denials for validation and failure context.
- [Scopes](./scopes.md): owns the unresolved placement and inheritance questions for implicitly created instances in nested containers.

## Context and problem

A binding explicitly records how DIBox should supply a requested dependency. When no binding matches a concrete class, DIBox can instead infer how to construct it from its annotated constructor and manage the resulting instance. This implicit self-binding avoids registrations that merely repeat information already present in type hints.

An unbound class can appear in two positions:

- A root is requested directly through the container and starts a new object graph.
- A transitive dependency is discovered from a constructor annotation while DIBox is building an already accepted graph.

Both positions use the same construction mechanism, but they express different intent. Accepting an implicit root expands the set of object graphs the container publicly agrees to create. Accepting an implicit transitive dependency lets constructor annotations describe the internals of a graph whose root has already been accepted.

One fallback for both positions loses one of those benefits. Always allowing implicit creation keeps setup minimal, but lets any constructable class become a container entrypoint. Always requiring bindings makes entrypoints and graph contents explicit, but forces the composition root to restate constructor structure even where no implementation, configuration, or lifetime decision exists. It also couples the composition root to graph internals: every small client, view, helper, or leaf service must be known, imported, and registered there.

Constructability is also not sufficient evidence of intent. Value types such as strings and paths have callable constructors whose default results are rarely meaningful dependencies. Applications may have their own categories that are technically constructable but should require an explicit declaration.

DIBox therefore needs independent control over root admission and transitive graph expansion, plus type-specific authorization for missing bindings.

## Decision drivers

Concrete constructor annotations already describe most dependency recipes. Explicit bindings add useful intent when they select an implementation, supply configuration or values, choose a lifecycle, name a variant, or declare an ownership boundary. Requiring them only to repeat an inferable recipe adds ceremony without information.

The policy must support progressive disclosure of complexity:

- A new user can wire a concrete graph without learning policy concepts.
- A growing application can make its roots explicit while retaining inferred internals.
- A production composition root can close unmatched graph expansion and selectively trust application-owned types or packages.

These stages should use one missing-binding model rather than overlapping controls that users must combine correctly.

## Design goals

- G1 — No duplicate graph declarations. Constructor annotations can wire concrete internals without corresponding registrations; bindings record additional intent.
- G2 — Progressive disclosure. `DIBox()` is useful without configuration, while stronger boundaries add one concept at a time.
- G3 — One authorization model. Root admission, transitive fallback, and type authorization belong to one missing-binding policy rather than overlapping modes and guards.
- G4 — Deterministic, order-independent semantics. The result of a root request should not depend on which graph or instance was resolved earlier. This goal is not yet fully met; see [Known limitation: cached request boundaries](#known-limitation-cached-request-boundaries).
- G5 — Discoverable graphs for diagnostics. Concrete root bindings give future validation a useful entrypoint set without a separate root declaration API; predicate bindings remain an open enumeration problem.

## Decision

`MissingBindingPolicy` is the single authorization surface used after binding lookup fails. `DIBox` accepts either a policy instance or one of three presets. A preset creates a fresh policy for that container, and `box.policy` exposes it for composition-root configuration.

The policy has independent defaults for roots and transitive dependencies, plus type-only allow and deny rules:

- `roots` controls whether an unbound request root may be created implicitly or requires an explicit binding.
- `unmatched_dependencies` controls whether a transitive dependency not matched by a rule may be created implicitly or requires a matching allow rule.
- Allow and deny rules classify requested runtime types by exact type, package, or predicate. Deny rules take precedence.

Explicit bindings bypass the policy. A matching binding already declares that construction and container ownership are intentional, including bindings for named values and types rejected from implicit creation.

The dependency graph remains responsible for looking up bindings, identifying root versus transitive position, compiling signatures, and attaching resolution context to denials. The policy is responsible only for authorizing a missing binding. Rule predicates remain type-only; graph position and argument names do not leak into the rule vocabulary.

## Presets

The presets are named configurations of the two fallbacks:

- `"open"` creates eligible unbound roots and unmatched dependencies implicitly. It is the default and the zero-configuration onboarding path.
- `"explicit-roots"` requires root bindings but creates eligible unmatched transitive dependencies implicitly. It makes the container surface reviewable without forcing the composition root to list graph internals.
- `"closed"` requires root bindings and requires allow rules for otherwise unmatched transitive dependencies. It is closed by default but can reopen trusted parts of the graph through type or package rules.

The presets are best understood as two axes rather than a single strictness scale. `"explicit-roots"` and `"open"` deliberately share the same transitive fallback; their difference is the request boundary.

## Root semantics

A root is a request that starts dependency graph construction at the container surface. Rootness belongs to the request position, not to the requested type. A type may be a valid implicit dependency in one graph while requiring a binding when requested directly.

With `roots="require-binding"`, an allow rule cannot turn an unbound type into a root. Root admission is an ownership-boundary decision; type rules authorize implicit construction inside an accepted graph. Keeping those concerns separate makes the composition root readable from its bindings.

The rejected alternative was an ownership-closure rule where anything reachable from a bound root also became a valid surface request. Although deterministic, that rule would silently widen the public container surface to every transitive implementation detail. The request-boundary rule is easier to teach and preserves the reason explicit roots exist.

Explicit roots provide benefits beyond stylistic strictness:

- They catch requests made against the wrong or incompletely configured container before DIBox silently reconstructs a second object graph.
- They make isolated test composition fail locally when a root binding is missing instead of resolving an unintended implementation.
- They make the planned `call()` safer for functions that mix injected and caller-supplied arguments: only explicitly bound parameters are filled, rather than every constructable annotation being treated as injectable.
- Concrete root bindings give future `validate()` and `graph()` APIs a useful entrypoint set while still permitting inferred internals.

## Type authorization

After the root boundary permits implicit creation, policy decisions follow these semantics:

1. Requests that are not runtime classes are rejected before configurable rules run.
2. Any matching deny rule rejects the type.
3. Otherwise, any matching allow rule authorizes the type.
4. An unmatched dependency is rejected when the policy requires an allow rule.
5. Known value types are rejected by the built-in fallback.
6. Other concrete types are authorized.

Package rules match a package and its subpackages at module boundaries, not by raw string prefix. Exact-type rules do not infer subclass intent. Predicate rules are the escape hatch for project-specific categories, and exceptions raised by user predicates propagate unchanged.

The built-in fallback rejects unmatched standard value types whose default construction is rarely meaningful for injection. An allow rule or explicit binding can authorize them when intentional; the exact built-in set belongs to the implementation.

## Why constructor-shape guards were retired

An earlier design treated zero-required-argument constructors as suspicious graph leaves. It caught unsafe defaults, but constructor shape did not express intent: legitimate views, helpers, and services were rejected too. Making every such internal leaf explicit coupled the composition root to implementation details and restored the registration boilerplate implicit self-binding was meant to remove.

The current design instead rejects common value types by default and uses type, package, or predicate rules for application-specific categories. Explicit bindings remain the declaration that construction is intentional; class style and constructor shape are not policy categories.

## Diagnostics and configuration timing

A policy denial becomes a `ResolutionError` containing the reason and the path from the requested root to the failing dependency. Named rules appear in the reason.

Policy rule lists are mutable, but graph compilation is cached. Configuration should therefore be completed before resolution. Mutations affect future policy evaluations; they do not invalidate graph nodes or instances already created under an earlier decision.

## Known limitation: cached request boundaries

G4 is not fully implemented. Root policy is evaluated while compiling an uncached missing binding, but hot paths return cached graph nodes or materialized instances without repeating binding lookup and policy evaluation. Consequently, a type first created implicitly as a transitive dependency may later be returned from a direct request even when the current policy requires explicit roots.

This is an order-dependence bug, but the naive fix would put binding searches and arbitrary user policy predicates on every hot `provide()` call. Instance retrieval is expected to remain cheap, so this correction is deferred rather than moving cold-path authorization work onto the hot path.

A future fix should preserve authorization provenance when a graph node or instance is first created, or provide an equivalent constant-time boundary check. The required invariant remains: prior transitive resolution must not promote an implicitly created type into an authorized root.

## Diagnostics boundary: predicate bindings

Predicate bindings intentionally count as explicit bindings and may therefore authorize any type they match at the root, regardless of the missing-binding policy. Because their possible matches cannot generally be enumerated, a future full-graph walk can discover concrete root bindings but cannot prove that it has listed every root accepted by predicates.

## Trade-offs and boundaries

- Inferred internals reduce composition-root coupling, but constructor changes can expand the managed graph without a corresponding binding change.
- Package and predicate rules describe trusted categories, not an exhaustive graph or a correctness proof. Broad rules intentionally authorize matching types added later.
- Within implicit creation, deny precedence creates hard exclusions. Exceptions require narrowing the deny rule or adding an explicit binding, which bypasses the policy.
- The policy authorizes implicit construction after lookup fails; it does not select implementations, supply configuration, choose lifetimes, or establish that a constructable class is semantically appropriate.

## Adjacent decisions

Nested containers add a separate placement question. Type hints infer a construction recipe, and this policy authorizes ownership, but neither says which container lifetime should own an implicitly created instance. Policy locality, inheritance, and placement remain scope decisions constrained by the rule that a dependency must live at least as long as its dependent.

## Superseded model

The former API split missing-binding behavior across resolution modes, a separate type-eligibility policy, and configurable guards. These overlapping controls were replaced by one policy because they could not directly express independent root admission and selectively trusted transitive expansion.