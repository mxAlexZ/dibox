from typing import Any, Callable

import pytest

from dibox import ANY_ARG, ANY_TYPE, BindingBox, ResolutionError
from dibox.dependency_graph import DependencyGraph, NodeKey, ResolutionMode


class Leaf:
    """A simple class with no dependencies. Intentionally all-default for ZDG check."""
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


@pytest.fixture(params=["permissive", "strict", "semi-strict"])
def resolution_mode(request: pytest.FixtureRequest) -> ResolutionMode:
    return request.param


class DependencyGraphBuildNodeTest:
    def test_build_node_walks_graph_from_root_to_leaf(self, resolution_mode: ResolutionMode):
        bindings = BindingBox()
        bindings.bind_many(Leaf, Branch, Root)
        graph = DependencyGraph(resolution_mode, bindings)

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
        assert [node.binding.sync_factory for node in nodes] == [Leaf, Branch, Root]
        assert [node.binding.async_factory for node in nodes] == [None, None, None]

    def test_build_node_returns_existing_node_on_repeated_request(self, resolution_mode: ResolutionMode):
        bindings = BindingBox()
        bindings.bind_many(Leaf, Branch, Root)
        graph = DependencyGraph(resolution_mode, bindings)

        root_node_1 = graph.build_node((Root, ANY_ARG))
        root_node_2 = graph.build_node((Root, ANY_ARG))

        assert root_node_1 is root_node_2

    @pytest.mark.parametrize(
        "requested_type",
        [
            "I am a string, not a type",
            Leaf | Branch,
            int,
            ANY_TYPE
        ],
    )
    def test_build_node_with_non_concrete_type_raises_value_error(self, requested_type: Any):
        bindings = BindingBox()
        graph = DependencyGraph("permissive", bindings)
        with pytest.raises(ResolutionError, match="not a concrete class") as exc_info:
            graph.build_node((requested_type, ANY_ARG))

        assert exc_info.value.resolution_stack == [(requested_type, ANY_ARG)]

    def test_bad_resolution_mode_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid resolution mode"):
            DependencyGraph("not-a-mode", BindingBox()) # type: ignore


class DependencyGraphWalkTest:
    def test_walk_yields_nodes_in_dependency_first_order(self):
        bindings = BindingBox()
        bindings.bind_many(Leaf, Branch, Root)
        graph = DependencyGraph("strict", bindings)
        root_node = graph.build_node((Root, ANY_ARG))

        steps = list(graph.walk(root_node, present_map={}))
        assert [step.node_key for step in steps] == [
            (Leaf, ANY_ARG),
            (Branch, ANY_ARG),
            (Root, ANY_ARG)
        ]
        assert [step.dependencies for step in steps] == [
            {},
            {"leaf": (Leaf, ANY_ARG)},
            {"branch": (Branch, ANY_ARG)},
        ]

    def test_walk_skips_present_branches(self):
        bindings = BindingBox()
        bindings.bind_many(Leaf, Branch, Root)
        graph = DependencyGraph("strict", bindings)
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
        graph = DependencyGraph("strict", bindings)
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


class DependencyGraphPermissiveModeTest:
    """Tests for behavior specific to permissive and semi-strict mode."""
    def test_unbound_root_produces_implicit_node(self):
        bindings = BindingBox()
        bindings.bind(Leaf)
        graph = DependencyGraph("permissive", bindings)

        root_node = graph.build_node((Root, ANY_ARG))
        assert root_node.key == (Root, ANY_ARG)
        assert len(root_node.sub_nodes) == 1
        assert root_node.sub_nodes_keys == {"branch": (Branch, ANY_ARG)}
        assert root_node.sub_nodes[0].key == (Branch, ANY_ARG)

    @pytest.mark.parametrize("resolution_mode", ["permissive", "semi-strict"])
    def test_unbound_transitive_dependency_produces_implicit_node(self, resolution_mode: ResolutionMode):
        bindings = BindingBox()
        bindings.bind_many(Root, Leaf)
        graph = DependencyGraph(resolution_mode, bindings)

        root_node = graph.build_node((Root, ANY_ARG))
        assert root_node.sub_nodes_keys["branch"] == (Branch, ANY_ARG)
        branch_node = root_node.sub_nodes[0]
        assert branch_node.key == (Branch, ANY_ARG)
        assert branch_node.sub_nodes_keys["leaf"] == (Leaf, ANY_ARG)


    @pytest.mark.parametrize("resolution_mode", ["permissive", "semi-strict"])
    def test_all_default_constructor_raises_resolution_error(self, resolution_mode: ResolutionMode):
        bindings = BindingBox()
        bindings.bind(Branch)
        graph = DependencyGraph(resolution_mode, bindings)

        with pytest.raises(ResolutionError, match="type without required parameters") as exc_info:
            graph.build_node((Branch, ANY_ARG))

        assert exc_info.value.resolution_stack == [(Branch, ANY_ARG), (Leaf, "leaf")]


class DependencyGraphStrictModeTest:
    """Tests for behavior specific to strict and semi-strict mode."""

    @pytest.mark.parametrize("resolution_mode", ["strict", "semi-strict"])
    def test_bound_root_produces_explicit_node(self, resolution_mode: ResolutionMode):
        bindings = BindingBox()
        bindings.bind_many(Leaf, Branch)
        graph = DependencyGraph(resolution_mode, bindings)

        branch_node = graph.build_node((Branch, ANY_ARG))
        assert branch_node.key == (Branch, ANY_ARG)
        assert branch_node.sub_nodes_keys == {"leaf": (Leaf, ANY_ARG)}


    @pytest.mark.parametrize("resolution_mode", ["strict", "semi-strict"])
    def test_unbound_root_raises_resolution_error(self, resolution_mode: ResolutionMode):
        bindings = BindingBox()
        graph = DependencyGraph(resolution_mode, bindings)

        with pytest.raises(ResolutionError, match="no binding found") as exc_info:
            graph.build_node((Root, ANY_ARG))

        assert exc_info.value.resolution_stack == [(Root, ANY_ARG)]


    def test_unbound_transitive_dependency_raises_resolution_error(self):
        bindings = BindingBox()
        bindings.bind_many(Root, Leaf) # Branch is not bound!
        graph = DependencyGraph("strict", bindings)
        with pytest.raises(ResolutionError, match="no binding found") as exc_info:
            graph.build_node((Root, ANY_ARG))

        assert exc_info.value.resolution_stack == [(Root, ANY_ARG), (Branch, "branch")]


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

class DependencyGraphPredicateBindingsTest:
    @pytest.mark.parametrize(
        "factory",
        [
            factory_no_args,
            factory_without_annotations,
            factory_with_type_arg,
            factory_with_type_any_arg,
            factory_with_type_specific_arg,
            async_factory_with_type_arg
        ] # type: ignore - untyped factories are intentional for testing
    )
    async def test_node_build_with_bound_type_argument(self, factory: Callable[..., Leaf]):
        bindings = BindingBox()
        bindings.bind(lambda t: t is Leaf, factory)
        graph = DependencyGraph("strict", bindings)

        leaf_node = graph.build_node((Leaf, ANY_ARG))
        res = await leaf_node.binding.call_async()
        assert isinstance(res, Leaf)
        assert res.tag == factory.__name__
