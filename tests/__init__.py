from functools import partial

from flake8_define_class_attributes.ast_walker import AssignNode

# For comparison tests, only the spec will matter
ASSIGN_NODE_P = partial(AssignNode, lineno=0, col_offset=1, end_lineno=None, end_col_offset=None)
