# flake8-define-class-attributes

[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/flake8-define-class-attributes/0.1.0?logo=python&logoColor=FFD43B)](https://pypi.org/project/flake8-define-class-attributes/)
[![PyPI](https://img.shields.io/pypi/v/flake8-define-class-attributes?logo=Python&logoColor=FFD43B)](https://pypi.org/project/flake8-define-class-attributes/)
[![PyPI - License](https://img.shields.io/pypi/l/flake8-define-class-attributes?color=magenta)](https://github.com/sco1/flake8-define-class-attributes/blob/main/LICENSE)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/sco1/flake8-define-class-attributes/main.svg)](https://results.pre-commit.ci/latest/github/sco1/flake8-define-class-attributes/main)

Check that class attributes are defined at the "top level" of your class. This is in the same spirit as Pylint's [`W0201` (`attribute-defined-outside-init`)](https://pylint.readthedocs.io/en/latest/user_guide/messages/warning/attribute-defined-outside-init.html) error, expanded to allow attribute declaration at the class level.

For example:

**Failing Code:**

```py
class Spaceship:
    def reset_location(self) -> None:
        self.xy = (0, 0)  # CLA001
```

**Passing Code:**

```py
class Spaceship:
    def __init__(self):
        self.xy = (0, 0)

    def reset_location(self):
        self.xy = (0, 0)

# --OR--

class Spaceship:
    xy: tuple[int, int]

    def reset_location(self):
        self.xy = (0, 0)
```

When using [dataclasses](https://docs.python.org/3/library/dataclasses.html), `__post_init__` methods are also considered when checking that an attribute has been defined.

## Installation

Install from PyPi with your favorite `pip` invocation:

```text
$ pip install flake8-define-class-attributes
```

It will then be run automatically as part of flake8.

You can verify it's being picked up by invoking the following in your shell:

```bash
$ flake8 --version
7.3.0 (flake8-define-class-attributes: 0.1.0, mccabe: 0.7.0, pycodestyle: 2.14.0, pyflakes: 3.4.0) CPython 3.13.5 on Darwin
```

## Warnings

| ID       | Description                                        |
|----------|----------------------------------------------------|
| `CLA001` | Attribute `<name>` not defined prior to assignment |

## Python Version Support

Beginning with Python 3.11, a best attempt is made to support Python versions until they reach EOL, after which support will be formally dropped by the next minor or major release of this package, whichever arrives first. The status of Python versions can be found [here](https://devguide.python.org/versions/).
