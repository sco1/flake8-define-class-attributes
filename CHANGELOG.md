# Changelog

Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (`<major>`.`<minor>`.`<patch>`)

## `[v0.2.2]`

### Fixed

* #6 Fixed unhandled exception when assignment contains a function call.

## `[v0.2.1]`

### Fixed

* #3 Fixed unhandled `IndexError` when attempting to resolve the name of the instance argument while inside functions nested within methods.

## `[v0.2.0]`

### Changed

* #1 Support alternative instance variable names for class methods
* #2 (Internal) Refactor AST walker to simplify logic flow

## `[v0.1.0]`

Initial release 🎉
