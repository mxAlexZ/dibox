from types import UnionType
from typing import Iterable, TypeVar, Union, get_args, get_origin

_V = TypeVar('_V')
DIMapKey = tuple[type | None, str | None]
MatchResult = tuple[_V, DIMapKey] | None

class DIMap(dict[DIMapKey, _V]):
    def find_match(self, key: DIMapKey) -> MatchResult[_V]:
        for subtype in _expand_type(key[0]):
            match = self._find_match(subtype, key[1])
            if match is not None:
                return match
        return None

    def _find_match(self, cls: type | None, name: str | None) -> MatchResult[_V]:
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

def _expand_type(type: type | None) -> Iterable[type | None]:
    origin_type = get_origin(type)
    if origin_type == UnionType or origin_type == Union:
        for sub_type in get_args(type):
            yield sub_type
    else:
        yield type
