import ast
import typing as t

import pytest

from flake8_define_class_attributes.ast_walker import FDCAVisitor, SelfAssignNode


class SourceWalkCase(t.NamedTuple):
    src: str
    truth_class_vars: set[str]
    truth_init_vars: set[str]
    truth_method_vars: list[SelfAssignNode]


EMPTY_CLASS = SourceWalkCase(
    src="""\
class Foo: ...
""",
    truth_class_vars=set(),
    truth_init_vars=set(),
    truth_method_vars=[],
)

CLASS_WITH_CLASSVAR = SourceWalkCase(
    src="""\
class Foo:
    a = 5
""",
    truth_class_vars={"a"},
    truth_init_vars=set(),
    truth_method_vars=[],
)

CLASS_WITH_INITVAR = SourceWalkCase(
    src="""\
class Foo:
    def __init__(self):
        self.a = 5
""",
    truth_class_vars=set(),
    truth_init_vars={"a"},
    truth_method_vars=[],
)


CLASS_WITH_METHODVAR = SourceWalkCase(
    src="""\
class Foo:
    def beans(self):
        self.a = 5
""",
    truth_class_vars=set(),
    truth_init_vars=set(),
    truth_method_vars=[
        SelfAssignNode(attr="a", lineno=3, col_offset=8, end_lineno=3, end_col_offset=18)
    ],
)

CLASS_WITH_METHODVAR_NON_SELF_ATTR = SourceWalkCase(
    src="""\
class Foo:
    def beans(self):
        abcd.a = 5
""",
    truth_class_vars=set(),
    truth_init_vars=set(),
    truth_method_vars=[],
)

CLASS_WITH_CLASSMETHOD = SourceWalkCase(
    src="""\
class Foo:
    @classmethod
    def beans(self):
        self.a = 5
""",
    truth_class_vars=set(),
    truth_init_vars=set(),
    truth_method_vars=[],
)

CLASS_WITH_STATICMETHOD = SourceWalkCase(
    src="""\
class Foo:
    @staticmethod
    def beans(self):
        self.a = 5
""",
    truth_class_vars=set(),
    truth_init_vars=set(),
    truth_method_vars=[],
)


CLASS_WITH_ALL_VAR = SourceWalkCase(
    src="""\
class Foo:
    a: 5

    def __init__(self):
        self.b = 5

    def beans(self):
        self.c = 5
""",
    truth_class_vars={"a"},
    truth_init_vars={"b"},
    truth_method_vars=[
        SelfAssignNode(attr="c", lineno=8, col_offset=8, end_lineno=8, end_col_offset=18)
    ],
)

CLASS_WITH_ALL_VAR_MULTI = SourceWalkCase(
    src="""\
class Foo:
    a: 1
    b: 2

    def __init__(self):
        self.c = 3
        self.d = 4

    def beans(self):
        self.e = 5
        self.f = 6
""",
    truth_class_vars={"a", "b"},
    truth_init_vars={"c", "d"},
    truth_method_vars=[
        SelfAssignNode(attr="e", lineno=10, col_offset=8, end_lineno=10, end_col_offset=18),
        SelfAssignNode(attr="f", lineno=11, col_offset=8, end_lineno=11, end_col_offset=18),
    ],
)


SIMPLE_DATACLASS = SourceWalkCase(
    src="""\
from dataclasses import dataclass

@dataclass
class Foo:
    a: int = 5
""",
    truth_class_vars={"a"},
    truth_init_vars=set(),
    truth_method_vars=[],
)

DATACLASS_WITH_POST_INIT = SourceWalkCase(
    src="""\
from dataclasses import dataclass

@dataclass
class Foo:
    a: int = 5

    def __post_init__(self):
        self.b = a
""",
    truth_class_vars={"a"},
    truth_init_vars={"b"},
    truth_method_vars=[],
)

SNEAKY_DEF_NOT_IN_CLASS = SourceWalkCase(
    src="""\
def beans(self):
    self.a = 5
""",
    truth_class_vars=set(),
    truth_init_vars=set(),
    truth_method_vars=[],
)


SRC_WALK_TEST_CASES = (
    EMPTY_CLASS,
    CLASS_WITH_CLASSVAR,
    CLASS_WITH_INITVAR,
    CLASS_WITH_METHODVAR,
    CLASS_WITH_METHODVAR_NON_SELF_ATTR,
    CLASS_WITH_CLASSMETHOD,
    CLASS_WITH_STATICMETHOD,
    CLASS_WITH_ALL_VAR,
    CLASS_WITH_ALL_VAR_MULTI,
    SIMPLE_DATACLASS,
    DATACLASS_WITH_POST_INIT,
    SNEAKY_DEF_NOT_IN_CLASS,
)


@pytest.mark.parametrize(
    ("src", "truth_class_vars", "truth_init_vars", "truth_method_vars"), SRC_WALK_TEST_CASES
)
def test_src_walk(
    src: str,
    truth_class_vars: set[str],
    truth_init_vars: set[str],
    truth_method_vars: list[SelfAssignNode],
) -> None:
    tree = ast.parse(src)
    visitor = FDCAVisitor()
    visitor.visit(tree)

    assert visitor.class_vars == truth_class_vars
    assert visitor.init_vars == truth_init_vars
    assert visitor.method_vars == truth_method_vars
