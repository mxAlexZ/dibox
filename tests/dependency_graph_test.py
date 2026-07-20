from typing import Any, Callable

import pytest

from dibox import ANY_ARG, ANY_TYPE, BindingBox, MissingBindingPolicy, ResolutionError
from dibox.dependency_graph import DependencyGraph, NodeKey


class Leaf:
    def __init__(self, tag: str = "default", *arg: Any, **kwargs: Any):
        self.tag = tag

class Branch:
    def __init__(self, leaf: Leaf):
        self.leaf = leaf

class Root:
    def __init__(self, branch: Branch):
        self.branch = branch

class LeftBranch:
    def __init__(self, leaf: Leaf):
        self.leaf = leaf

class RightBranch:
    def __init__(self, leaf: Leaf):
        self.leaf = leaf


class RootWithSharedDependency:
    def __init__(self, left: LeftBranch, right: RightBranch):
        self.left = left
        self.right = right

class DependencyGraphBuildNodeTest:
    def test_build_node_walks_graph_from_root_to_leaf(self):
        bindings = BindingBox()
        bindings.bind_many(Leaf, Branch, Root)
        graph = DependencyGraph(bindings)

        root_node = graph.build_node((Root, ANY_ARG))
        branch_node = root_node.sub_nodes[0]
        leaf_node = branch_node.sub_nodes[0]
        nodes = [leaf_node, branch_node, root_node]

        assert [node.key for node in nodes] == [
            (Leaf, ANY_ARG),
            (Branch, ANY_ARG),
            (Root, ANY_ARG),
        ]
        assert [node.sub_nodes_keys for node in nodes] == [
            {},
            {"leaf": (Leaf, ANY_ARG)},
            {"branch": (Branch, ANY_ARG)},
        ]
        assert [node.binding.name for node in nodes] == ["Leaf", "Branch", "Root"]

    def test_build_node_returns_cached_node_for_repeated_query(self):
        bindings = BindingBox()
        bindings.bind_many(Leaf, Branch, Root)
        graph = DependencyGraph(bindings)

        root_node_1 = graph.build_node((Root, ANY_ARG))
        root_node_2 = graph.build_node((Root, ANY_ARG))

        assert root_node_1 is root_node_2

    def test_build_node_surfaces_non_concrete_request_denial(self):
        bindings = BindingBox()
        graph = DependencyGraph(bindings)
        with pytest.raises(
            ResolutionError,
            match="implicit creation denied because request is not a concrete class",
        ) as exc_info:
            graph.build_node((ANY_TYPE, ANY_ARG))

        assert exc_info.value.resolution_stack == [(ANY_TYPE, ANY_ARG)]

    def test_build_node_wraps_non_introspectable_factory_signature_error(self):
        bindings = BindingBox()
        bindings.bind(Leaf, factory=str)
        graph = DependencyGraph(bindings)

        with pytest.raises(ResolutionError, match="cannot introspect signature") as exc_info:
            graph.build_node((Leaf, ANY_ARG))

        assert isinstance(exc_info.value.__cause__, ValueError)
        assert exc_info.value.resolution_stack == [(Leaf, ANY_ARG)]

class DependencyGraphWalkTest:
    def test_walk_yields_nodes_in_dependency_first_order(self):
        bindings = BindingBox()
        bindings.bind_many(Leaf, Branch, Root)
        graph = DependencyGraph(bindings, policy="closed")
        root_node = graph.build_node((Root, ANY_ARG))

        steps = list(graph.walk(root_node, present_map={}))
        assert [step.node_key for step in steps] == [
            (Leaf, ANY_ARG),
            (Branch, ANY_ARG),
            (Root, ANY_ARG),
        ]
        assert [step.dependencies for step in steps] == [
            {},
            {"leaf": (Leaf, ANY_ARG)},
            {"branch": (Branch, ANY_ARG)},
        ]

    def test_walk_skips_present_branches(self):
        bindings = BindingBox()
        bindings.bind_many(Leaf, Branch, Root)
        graph = DependencyGraph(bindings, policy="closed")
        root_node = graph.build_node((Root, ANY_ARG))

        present_map: dict[NodeKey, object] = {
            (Leaf, ANY_ARG): object(),
            (Branch, ANY_ARG): object(),
        }
        steps = list(graph.walk(root_node, present_map))

        assert [step.node_key for step in steps] == [(Root, ANY_ARG)]
        assert steps[0].dependencies == {"branch": (Branch, ANY_ARG)}

    def test_walk_emits_shared_dependency_only_once(self):
        bindings = BindingBox()
        bindings.bind_many(Leaf, LeftBranch, RightBranch, RootWithSharedDependency)
        graph = DependencyGraph(bindings, policy="closed")
        root_node = graph.build_node((RootWithSharedDependency, ANY_ARG))

        steps = list(graph.walk(root_node, present_map={}))

        assert [step.node_key for step in steps] == [
            (Leaf, ANY_ARG),
            (LeftBranch, ANY_ARG),
            (RightBranch, ANY_ARG),
            (RootWithSharedDependency, ANY_ARG),
        ]
        assert [step.dependencies for step in steps] == [
            {},
            {"leaf": (Leaf, ANY_ARG)},
            {"leaf": (Leaf, ANY_ARG)},
            {"left": (LeftBranch, ANY_ARG), "right": (RightBranch, ANY_ARG)},
        ]


class DependencyGraphPolicyBoundaryTest:
    def test_explicit_roots_policy_rejects_unbound_root(self):
        graph = DependencyGraph(BindingBox(), policy="explicit-roots")

        with pytest.raises(ResolutionError, match="root requires explicit binding") as exc_info:
            graph.build_node((Leaf, ANY_ARG))

        assert exc_info.value.resolution_stack == [(Leaf, ANY_ARG)]

    def test_explicit_roots_policy_allows_unbound_transitive_dependency(self):
        bindings = BindingBox()
        bindings.bind(Root)
        graph = DependencyGraph(bindings, policy="explicit-roots")

        root_node = graph.build_node((Root, ANY_ARG))

        assert root_node.sub_nodes_keys == {"branch": (Branch, ANY_ARG)}
        assert root_node.sub_nodes[0].key == (Branch, ANY_ARG)

    def test_policy_denial_for_unbound_transitive_dependency_includes_resolution_stack(self):
        bindings = BindingBox()
        bindings.bind(Branch)
        graph = DependencyGraph(bindings, policy="closed")

        with pytest.raises(ResolutionError, match="dependency requires an allow rule") as exc_info:
            graph.build_node((Branch, ANY_ARG))

        assert exc_info.value.resolution_stack == [(Branch, ANY_ARG), (Leaf, "leaf")]

    def test_allow_rule_authorizes_unbound_transitive_dependency(self):
        policy = MissingBindingPolicy.from_preset("closed")
        policy.allow_type(Leaf)
        bindings = BindingBox()
        bindings.bind(Branch)
        graph = DependencyGraph(bindings, policy)

        branch_node = graph.build_node((Branch, ANY_ARG))

        assert branch_node.sub_nodes_keys == {"leaf": (Leaf, ANY_ARG)}

    def test_explicit_binding_bypasses_policy(self):
        policy = MissingBindingPolicy(roots="require-binding", unmatched_dependencies="require-allow-rule")
        policy.deny_type(Leaf)
        bindings = BindingBox()
        bindings.bind(Leaf)
        graph = DependencyGraph(bindings, policy)

        assert graph.build_node((Leaf, ANY_ARG)).binding.name == "Leaf"

    def test_policy_predicate_exception_propagates_unchanged(self):
        def broken_policy(_requested_type: type[Any]) -> bool:
            raise TypeError("broken policy")

        policy = MissingBindingPolicy()
        policy.deny_if(broken_policy)
        graph = DependencyGraph(BindingBox(), policy)

        with pytest.raises(TypeError, match="broken policy"):
            graph.build_node((Leaf, ANY_ARG))


class DependencyGraphFutureAnnotationsTest:
    def test_future_annotations_do_not_break_dependency_resolution(self):
        from future_annotations_classes import FutureBranch, FutureLeaf
        # With `from __future__ import annotations`, all annotations are stored as strings
        bindings = BindingBox()
        bindings.bind_many(FutureLeaf, FutureBranch)
        graph = DependencyGraph(bindings, policy="closed")

        branch_node = graph.build_node((FutureBranch, ANY_ARG))
        assert branch_node.key == (FutureBranch, ANY_ARG)
        assert branch_node.sub_nodes_keys == {"leaf": (FutureLeaf, ANY_ARG)}


def factory_no_args() -> Leaf:
    return Leaf("factory_no_args")

def factory_without_annotations(t) -> Leaf: # type: ignore
    return t("factory_without_annotations") # type: ignore

def factory_with_type_arg(t: type) -> Leaf:
    return t("factory_with_type_arg") # type: ignore

def factory_with_type_any_arg(t: type[Any]) -> Leaf:
    return t("factory_with_type_any_arg") # type: ignore

def factory_with_type_specific_arg(t: type[Leaf]) -> Leaf:
    return t("factory_with_type_specific_arg")

async def async_factory_with_type_arg(t: type[Leaf]) -> Leaf:
    return t("async_factory_with_type_arg")


class TestDependencyGraphPredicateBindingContracts:
    @pytest.mark.parametrize(
        "factory",
        [
            factory_no_args,
            factory_without_annotations,
            factory_with_type_arg,
            factory_with_type_any_arg,
            factory_with_type_specific_arg,
            async_factory_with_type_arg,
        ],  # type: ignore[list-item] - intentionally includes untyped factories for specialization coverage
    )
    async def test_predicate_factory_with_type_first_parameter_receives_requested_type(
        self,
        factory: Callable[..., Leaf],
    ):
        bindings = BindingBox()
        bindings.bind(lambda t: t is Leaf, factory)
        graph = DependencyGraph(bindings, policy="closed")

        leaf_node = graph.build_node((Leaf, ANY_ARG))
        res = await leaf_node.binding.call_async()
        assert isinstance(res, Leaf)
        assert res.tag == factory.__name__

    def test_factory_with_non_type_first_arg_keeps_dependency_resolution(self):
        class FactoryDependency:
            pass
        # A predicate factory whose first parameter is a dependency (not a `type` argument)
        def factory_with_dependency_arg(dependency: FactoryDependency) -> Leaf:
            return Leaf("factory_with_dependency_arg")
        bindings = BindingBox()
        bindings.bind(lambda t: t is Leaf, factory_with_dependency_arg)
        graph = DependencyGraph(bindings, policy="open")

        leaf_node = graph.build_node((Leaf, ANY_ARG))
        assert leaf_node.sub_nodes_keys == {"dependency": (FactoryDependency, ANY_ARG)}
