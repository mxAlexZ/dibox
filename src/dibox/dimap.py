from types import UnionType
from typing import Any, Iterable, TypeVar, Union, cast, get_args, get_origin

_T = TypeVar('_T')
_V = TypeVar('_V')
TypeQuery = type[_T] | UnionType | None
ArgNameQuery = str | None
DIMapKey = tuple[type[_T] | None, ArgNameQuery]
MatchResult = tuple[_V, DIMapKey[_T]] | None

class DIMap(dict[DIMapKey[Any], _V]):
    """
    A dictionary-like container, allowing retrieval by argument type and name.
    """
    def find_match(self, type_request: TypeQuery[_T], name_request: ArgNameQuery) -> MatchResult[_V, _T]:
        for subtype in _expand_type(type_request):  # iterate through all subtypes if requested type is an union type
            match = self._find_match(subtype, name_request)
            if match is not None:
                return match
        return None

    def _find_match(self, cls: type[_T] | None, name: ArgNameQuery) -> MatchResult[_V, _T]:
        exact_match = self.get((cls, name))
        if exact_match is not None:
            return exact_match, (cls, name)
        if name is not None:
            cls_match = self.get((cls, None))
            if cls_match is not None:
                return cls_match, (cls, None)
        if cls is not None:
            name_match = self.get((None, name))
            if name_match is not None:
                return name_match, (None, name)
        return None

def _expand_type(requested_type: TypeQuery[_T]) -> Iterable[type[_T] | None]:
    origin_type = get_origin(requested_type)
    if origin_type == UnionType or origin_type == Union:
        for sub_type in get_args(requested_type):
            yield sub_type
    else:
        yield cast(type[_T] | None, requested_type)
