import ast
import typing as t

import pytest

from flake8_define_class_attributes.ast_walker import SelfAssignNode
from flake8_define_class_attributes.checker import CLA001, ClassAttributeChecker, FORMATTED_ERROR


def test_err_to_flake8() -> None:
    err = CLA001(
        SelfAssignNode(attr="a", lineno=0, col_offset=1, end_lineno=None, end_col_offset=None)
    )
    TRUTH_OUT = (
        0,
        1,
        "CLA001 Attribute 'a' not defined prior to assignment",
        ClassAttributeChecker,
    )

    assert err.to_flake8() == TRUTH_OUT


class SourceCheckCase(t.NamedTuple):
    src: str
    truth_errors: set[FORMATTED_ERROR]  # May not be in order


# These should not yield errors
EMPTY_CLASS = SourceCheckCase(
    src="""\
class Foo: ...
""",
    truth_errors=set(),
)

CLASS_WITH_CLASSVAR = SourceCheckCase(
    src="""\
class Foo:
    a = 5
""",
    truth_errors=set(),
)

CLASS_WITH_INITVAR = SourceCheckCase(
    src="""\
class Foo:
    def __init__(self):
        self.a = 5
""",
    truth_errors=set(),
)

CLASS_WITH_CLASSMETHOD = SourceCheckCase(
    src="""\
class Foo:
    @classmethod
    def beans(self):
        self.a = 5
""",
    truth_errors=set(),
)

CLASS_WITH_STATICMETHOD = SourceCheckCase(
    src="""\
class Foo:
    @staticmethod
    def beans(self):
        self.a = 5
""",
    truth_errors=set(),
)

SIMPLE_DATACLASS = SourceCheckCase(
    src="""\
from dataclasses import dataclass

@dataclass
class Foo:
    a: int = 5
""",
    truth_errors=set(),
)

DATACLASS_WITH_POST_INIT = SourceCheckCase(
    src="""\
from dataclasses import dataclass

@dataclass
class Foo:
    a: int = 5

    def __post_init__(self):
        self.b = a
""",
    truth_errors=set(),
)

CLASS_WITH_DEFINED_METHODVAR_AS_CLASSVAR = SourceCheckCase(
    src="""\
class Foo:
    a: int

    def beans(self):
        self.a = 5
""",
    truth_errors=set(),
)

CLASS_WITH_DEFINED_METHODVAR_AS_INITVAR = SourceCheckCase(
    src="""\
class Foo:
    def __init__(self):
        self.a = 1

    def beans(self):
        self.a = 5
""",
    truth_errors=set(),
)

CLASS_WITH_METHOD_NON_SELF_ATTR = SourceCheckCase(
    src="""\
class Foo:
    def beans(self):
        abcd.a = 5
""",
    truth_errors=set(),
)

SNEAKY_DEF_NOT_IN_CLASS = SourceCheckCase(
    src="""\
def beans(self):
    self.a = 5
""",
    truth_errors=set(),
)

CLASS_WITH_MIXED_INSTANCE_VARNAME = SourceCheckCase(
    src="""\
class Foo:
    def __init__(self):
        self.a = 1

    def beans(slef):
        slef.a = 5
""",
    truth_errors=set(),
)

CLASS_WITH_NESTED_DEFINED_VAR = SourceCheckCase(
    src="""\
class Foo:
    a: int = 1

    def beans(self):
        def deep_beans():
            self.a = 1
""",
    truth_errors=set(),
)

# These should yield errors
CLASS_WITH_UNDEFINED_VAR = SourceCheckCase(
    src="""\
class Foo:
    def beans(self):
        self.a = 5
""",
    truth_errors={
        CLA001(
            SelfAssignNode(attr="a", lineno=3, col_offset=8, end_lineno=None, end_col_offset=None)
        ).to_flake8()
    },
)

CLASS_WITH_MULTI_UNDEFINED_VAR = SourceCheckCase(
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
    truth_errors={
        CLA001(
            SelfAssignNode(attr="e", lineno=10, col_offset=8, end_lineno=None, end_col_offset=None)
        ).to_flake8(),
        CLA001(
            SelfAssignNode(attr="f", lineno=11, col_offset=8, end_lineno=None, end_col_offset=None)
        ).to_flake8(),
    },
)

CLASS_WITH_NESTED_UNDEFINED_VAR = SourceCheckCase(
    src="""\
class Foo:
    def beans(self):
        def deep_beans():
            self.a = 1
""",
    truth_errors={
        CLA001(
            SelfAssignNode(attr="a", lineno=4, col_offset=12, end_lineno=None, end_col_offset=None)
        ).to_flake8(),
    },
)


SRC_CHECK_CASES = (
    # These shouldn't yield any errors
    EMPTY_CLASS,
    CLASS_WITH_CLASSVAR,
    CLASS_WITH_INITVAR,
    CLASS_WITH_CLASSMETHOD,
    CLASS_WITH_STATICMETHOD,
    SIMPLE_DATACLASS,
    DATACLASS_WITH_POST_INIT,
    CLASS_WITH_DEFINED_METHODVAR_AS_CLASSVAR,
    CLASS_WITH_DEFINED_METHODVAR_AS_INITVAR,
    CLASS_WITH_METHOD_NON_SELF_ATTR,
    SNEAKY_DEF_NOT_IN_CLASS,
    CLASS_WITH_MIXED_INSTANCE_VARNAME,
    CLASS_WITH_NESTED_DEFINED_VAR,
    # These should yield errors
    CLASS_WITH_UNDEFINED_VAR,
    CLASS_WITH_MULTI_UNDEFINED_VAR,
    CLASS_WITH_NESTED_UNDEFINED_VAR,
)


@pytest.mark.parametrize(("src", "truth_errors"), SRC_CHECK_CASES)
def test_src_check(src: str, truth_errors: set[FORMATTED_ERROR]) -> None:
    tree = ast.parse(src)
    checker = ClassAttributeChecker(tree)

    errs = set(checker.run())
    assert errs == truth_errors  # Might have to use an order-agnostic comparison here
