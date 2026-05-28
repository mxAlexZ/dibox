import inspect
from collections.abc import Mapping
from typing import Any, Generator, Literal, NamedTuple, Protocol, cast, get_origin

from .binding_box import BindingMatch
from .binding_record import BindingRecord
from .dimap import ANY_ARG, DIMap, DIMapKey, TypeQuery, WildArgName
from .resolution_error import ResolutionError
from .resolution_stack import ResolutionStack

NodeKey = DIMapKey[Any]
NodeQuery = tuple[TypeQuery[Any], WildArgName]
ResolutionMode = Literal["permissive", "strict", "semi-strict"]


class BindingLookup(Protocol):
    def find_binding(
        self,
        requested_type: TypeQuery[Any],
        arg_name: WildArgName,
    ) -> BindingMatch | None:
        ...


class GraphNode(NamedTuple):
    key: DIMapKey[Any]
    binding: BindingRecord
    sub_nodes: list["GraphNode"]
    sub_nodes_keys: dict[str, NodeKey]


class WalkResult(NamedTuple):
    node_key: NodeKey
    binding: BindingRecord
    dependencies: dict[str, NodeKey]
    resolution_stack: ResolutionStack


class DependencyGraph:
    """Internal graph builder for dependency resolution."""
    def __init__(self, mode: ResolutionMode, bindings: BindingLookup) -> None:
        if mode not in ("permissive", "strict", "semi-strict"):
            raise ValueError(f"Invalid resolution mode: {mode}")
        self._resolution_mode: ResolutionMode = mode
        self._node_map = DIMap[GraphNode]()
        self._bindings = bindings
        self._is_closed = False


    def build_node(self, node_query: NodeQuery) -> GraphNode:
        """Build and cache the dependency graph for node_query.

        Returns the root GraphNode.
        """
        return self._build_node_recursive(node_query, ResolutionStack())

    def walk(self, node: GraphNode, present_map: Mapping[NodeKey, Any]) -> Generator[WalkResult, None, None]:
        """Yield nodes in dependency-first order.

        Dependencies for each yielded node are either in `present_map` or yielded earlier.
        Use `present_map` to skip already-available nodes. Yields unique nodes per call.
        """
        resolution_stack = ResolutionStack()
        emitted_keys: set[NodeKey] = set()
        yield from self._walk_recursive(
            node,
            resolution_stack,
            present_map,
            emitted_keys,
        )

    def _walk_recursive(
        self,
        node: GraphNode,
        resolution_stack: ResolutionStack,
        present_map: Mapping[NodeKey, Any],
        emitted_keys: set[NodeKey],
    ) -> Generator[WalkResult, None, None]:
        if node.key in present_map or node.key in emitted_keys:
            return

        resolution_stack.append(node.key)
        try:
            for sub_node in node.sub_nodes:
                yield from self._walk_recursive(sub_node, resolution_stack, present_map, emitted_keys)
            emitted_keys.add(node.key)
            yield WalkResult(node.key, node.binding, node.sub_nodes_keys, resolution_stack)
        finally:
            resolution_stack.pop()

    def _build_node_recursive(self, node_query: NodeQuery, resolution_stack: ResolutionStack) -> GraphNode:
        existing_node, _ = self._node_map.find_match(*node_query)
        if existing_node is not None:
            return existing_node

        resolution_stack.append(node_query)
        try:
            binding_record, map_position = self._create_binding(node_query, resolution_stack)
            dependencies = self._get_dependencies_from_signature(binding_record.signature)
            sub_nodes_links: dict[str, NodeKey] = {}
            sub_nodes: list[GraphNode] = []
            for sub_node_query in dependencies:
                sub_node = self._build_node_recursive(sub_node_query, resolution_stack)
                sub_nodes.append(sub_node)
                sub_nodes_links[sub_node_query[1]] = sub_node.key
            new_node = GraphNode(map_position, binding_record, sub_nodes, sub_nodes_links)
            self._node_map[map_position] = new_node
            return new_node
        finally:
            resolution_stack.pop()

    def _create_binding(self, node_query: NodeQuery, resolution_stack: ResolutionStack) -> tuple[BindingRecord, NodeKey]:
        # binding_record, map_position = self._bindings.find_binding(*node_query)
        binding_match = self._bindings.find_binding(*node_query)
        if binding_match is not None:
            binding_record = binding_match.binding
            if binding_match.via_predicate:
                # for predicate-based binding, make a specialized binding record with bound constructed type.
                binding_record = self._bind_factory_type_argument(binding_match.key[0], binding_record)
            return binding_record, binding_match.key
        if not self._implicit_binding_allowed(resolution_stack):
            raise ResolutionError("no binding found", resolution_stack)
        implicit_binding, matched_type = self._make_implicit_binding_record(node_query[0], resolution_stack)
        implicit_binding.name = f"{implicit_binding.name} (implicit)"
        node_position = (matched_type, ANY_ARG)
        return implicit_binding, node_position

    def _implicit_binding_allowed(self, resolution_stack: ResolutionStack) -> bool:
        match self._resolution_mode:
            case "strict":
                return False
            case "semi-strict":
                return len(resolution_stack) > 1
            case _:
                return True

    def _make_implicit_binding_record(
        self,
        requested_type: TypeQuery[Any],
        resolution_stack: ResolutionStack,
    ) -> tuple[BindingRecord, type[Any]]:
        if not isinstance(requested_type, type):
            raise ResolutionError("requested type is not a concrete class", resolution_stack)
        try:
            signature = inspect.signature(requested_type)
            # Zero-dependency guard: require at least one required constructor parameter
            # to prevent silent leaf node creation.
            if not any(
                parameter.default == inspect.Parameter.empty
                and parameter.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
                for parameter in signature.parameters.values()
            ):
                raise ResolutionError("type without required parameters needs explicit binding", resolution_stack)
        except (ValueError, TypeError):
            raise ResolutionError("requested type is not a concrete class", resolution_stack) from None
        return (
            BindingRecord(requested_type),
            requested_type,
        )

    @staticmethod
    def _get_dependencies_from_signature(signature: inspect.Signature) -> list[tuple[TypeQuery[Any], str]]:
        dependencies: list[tuple[TypeQuery[Any], str]] = []
        for parameter in signature.parameters.values():
            if (
                parameter.default == inspect.Parameter.empty
                and parameter.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
                and parameter.annotation != inspect.Parameter.empty
            ):
                dependencies.append((cast(TypeQuery[Any], parameter.annotation), parameter.name))
        return dependencies

    @staticmethod
    def _bind_factory_type_argument(type_to_create: Any, binding_record: BindingRecord) -> BindingRecord:
        first_parameter = next(iter(binding_record.signature.parameters.values()), None)
        if first_parameter is None:
            return binding_record

        parameter_type = first_parameter.annotation
        if (
            parameter_type != inspect.Parameter.empty
            and parameter_type is not type
            and get_origin(parameter_type) is not type
        ):
            return binding_record
        specialization_tag = getattr(type_to_create, "__name__", str(type_to_create))
        binding_record = binding_record.partial(f"{binding_record.name}[{specialization_tag}]", args=(type_to_create,))
        return binding_record
