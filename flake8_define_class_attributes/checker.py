import ast
import typing as t

from flake8_define_class_attributes import __version__

FORMATTED_ERROR: t.TypeAlias = tuple[int, int, str, t.Type[t.Any]]


class CLA001:
    def __init__(self) -> None:
        raise NotImplementedError

    def to_flake8(self) -> FORMATTED_ERROR:
        raise NotImplementedError


class ClassAttributeChecker:
    name = "flake8-define-class-attributes"
    version = __version__

    def __init__(self, tree: ast.Module | None) -> None:
        pass

    def run(self) -> t.Generator[FORMATTED_ERROR, None, None]:
        pass
