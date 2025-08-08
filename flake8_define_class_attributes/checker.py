import ast
import typing as t

from flake8_define_class_attributes import __version__
from flake8_define_class_attributes.ast_walker import FDCAVisitor, SelfAssignNode

FORMATTED_ERROR: t.TypeAlias = tuple[int, int, str, t.Type[t.Any]]


class CLA001:  # noqa: D101
    def __init__(self, node: SelfAssignNode) -> None:
        self.attr_name = node.attr

        self.msg = f"CLA001 Attribute '{self.attr_name}' not defined prior to assignment"
        self.lineno = node.lineno
        self.col_offset = node.col_offset

    def to_flake8(self) -> FORMATTED_ERROR:  # noqa: D102
        return (self.lineno, self.col_offset, self.msg, ClassAttributeChecker)


class ClassAttributeChecker:  # noqa: D101
    name = "flake8-define-class-attributes"
    version = __version__

    def __init__(self, tree: ast.Module | None) -> None:
        self.tree = tree

    def run(self) -> t.Generator[FORMATTED_ERROR, None, None]:
        """
        This method is called by flake8 to perform the actual check(s) on the source code.

        This should yield tuples with the following information:
            (line number, column number, message, checker type)
        """
        if self.tree is not None:
            visitor = FDCAVisitor()
            visitor.visit(self.tree)
        else:
            return

        for a in visitor.method_vars:
            if (a.attr in visitor.init_vars) or (a.attr in visitor.class_vars):
                continue

            yield CLA001(a).to_flake8()
