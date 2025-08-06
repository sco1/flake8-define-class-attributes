import ast
import typing as t

AST_FUNC_NODES_T: t.TypeAlias = ast.FunctionDef | ast.AsyncFunctionDef
AST_DEF_NODES_T: t.TypeAlias = AST_FUNC_NODES_T | ast.ClassDef
AST_ASSIGN_NODES_T: t.TypeAlias = ast.Assign | ast.AnnAssign | ast.AugAssign


def has_special_decorator(node: AST_FUNC_NODES_T) -> bool:
    """Return `True` if the node is decorated with `@classmethod` or `@staticmethod`."""
    for d in node.decorator_list:
        if isinstance(d, ast.Name):
            if d.id in {"classmethod", "staticmethod"}:
                return True

    return False


class AssignSpec(t.NamedTuple):
    """
    Helper container for an assignment statement's leftmost components.

    For non-attribute assignment (e.g. `a = 5` or `a[1] = 5`), the `attr` component should be passed
    as an empty string (`""`).
    """

    base: str
    attr: str


def resolve_attribute(base_node: ast.Attribute) -> AssignSpec:
    """
    Resolve the two leftmost components of the provided `Attribute` node.

    For example, the following nodes should all resolve to `AssignSpec("self", "a")`:

    ```
    self.a = 42
    self.a[1] = 42
    self.a.b = 42
    self.a.b[1].c.d = 42
    self.a.b.c.d.e.f.g = 42
    ```
    """
    # With nested attribute access, the leftmost components that we're interested in end up being
    # at the deepest part of the base node's value component, so we have to go spelunking
    node: ast.AST = base_node
    while isinstance(node, (ast.Attribute, ast.Subscript)):
        if isinstance(node, ast.Attribute):
            attr = node.attr
            node = node.value
        else:
            node = node.value

    # If we've gotten here, we should either have the base node in the simple case, or the leftmost
    # attribute access of a nested node
    if isinstance(node, ast.Name):
        return AssignSpec(node.id, attr)
    else:
        # Not sure if this can actually be reached
        raise ValueError(f"Unexpected node type: {type(node)}")


def resolve_assign(node: ast.AST) -> set[AssignSpec]:
    """
    Resolve an assignment statement into its lefmost components.

    Top level calls are expected to pass an instance of `ast.Assign`, `ast.AnnAssign`, or
    `ast.AugAssign`.
    """
    assigned = set()
    match node:
        case ast.Assign():
            for n in node.targets:
                assigned.update(resolve_assign(n))
        case ast.AnnAssign() | ast.AugAssign():
            assigned.update(resolve_assign(node.target))
        case ast.Tuple() | ast.List():
            for n in node.elts:
                assigned.update(resolve_assign(n))
        case ast.Attribute():
            assigned.add(resolve_attribute(node))
        case ast.Name():
            assigned.add(AssignSpec(node.id, ""))
        case ast.Subscript():
            assigned.update(resolve_assign(node.value))
        case _:
            print("Unhandled node:")
            print(ast.dump(node))

    return assigned


class FDCAVisitor(ast.NodeVisitor):
    _context: list[AST_DEF_NODES_T]
    _n_contained_classdef: int

    _class_vars: set[AssignSpec]
    _init_vars: set[AssignSpec]

    def __init__(self) -> None:
        self._context = []
        self._n_contained_classdef = 0

        self._class_vars = set()
        self._init_vars = set()

    def switch_context(self, node: AST_DEF_NODES_T) -> None:
        is_classdef = isinstance(node, ast.ClassDef)
        if is_classdef:  # For downstream bookkeeping so we don't have to iterate through _context
            self._n_contained_classdef += 1

        if (not is_classdef) and (self._n_contained_classdef > 0):
            if has_special_decorator(node):  # type: ignore[arg-type]  # Already narrowed
                # Skip classmethod & staticmethod
                return

        self._context.append(node)
        self.generic_visit(node)
        popped = self._context.pop()

        if isinstance(popped, ast.ClassDef):
            self._n_contained_classdef -= 1

    def visit_assign(self, node: AST_ASSIGN_NODES_T) -> None:
        # Rather than checking if any context is a classdef, we have a bookkeeping counter upstream
        if self._n_contained_classdef == 0:
            return

        if isinstance(self._context[-1], ast.ClassDef):
            print("Class var", resolve_assign(node))
            self._class_vars.update(resolve_assign(node))
        else:
            method_name = self._context[-1].name
            if method_name in {"__init__", "__post_init__"}:
                print("Init Var", resolve_assign(node))
                self._init_vars.update(resolve_assign(node))
            else:
                print("Var from method: '{method_name}'", resolve_assign(node))

    visit_FunctionDef = switch_context
    visit_AsyncFunctionDef = switch_context
    visit_ClassDef = switch_context

    visit_Assign = visit_assign
    visit_AnnAssign = visit_assign
    visit_AugAssign = visit_assign
