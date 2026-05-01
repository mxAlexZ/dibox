from enum import Enum
from types import UnionType
from typing import Any, Iterable, TypeVar, Union, cast, get_args, get_origin

_T = TypeVar('_T')
_V = TypeVar('_V')


class MatchAny(Enum):
    ANY = 0

ANY_TYPE = MatchAny.ANY
ANY_ARG = MatchAny.ANY

WildType = type[_T] | MatchAny
TypeQuery = WildType[_T] | UnionType
WildArgName = str | MatchAny
DIMapKey = tuple[WildType[_T], WildArgName]
MatchResult = tuple[_V | None, DIMapKey[_T]]

class DIMap(dict[DIMapKey[Any], _V]):
    """
    A dictionary-like container, allowing retrieval by argument type and name.
    """
    def find_match(self, type_request: TypeQuery[_T], name_request: WildArgName) -> MatchResult[_V, _T]:
        for subtype in _explode(type_request):  # iterate through all subtypes if requested type is an union type
            value, key = self._find_match(subtype, name_request)
            if value is not None:
                return value, key
        return None, (ANY_TYPE, ANY_ARG)

    def _find_match(self, req_type: WildType[_T], req_name: WildArgName) -> MatchResult[_V, _T]:
        exact_match = self.get((req_type, req_name))
        if exact_match is not None:
            return exact_match, (req_type, req_name)
        cls_match = self.get((req_type, ANY_ARG))
        if cls_match is not None:
            return cls_match, (req_type, ANY_ARG)
        name_match = self.get((ANY_TYPE, req_name))
        if name_match is not None:
            return name_match, (ANY_TYPE, req_name)
        return None, (ANY_TYPE, ANY_ARG)

def _explode(requested_type: TypeQuery[_T]) -> Iterable[type[_T] | MatchAny]:
    origin_type = get_origin(requested_type)
    if origin_type == UnionType or origin_type == Union:
        for sub_type in get_args(requested_type):
            yield sub_type
    else:
        yield cast(type[_T] | MatchAny, requested_type)
