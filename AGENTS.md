## Rules

### Rule: Fixing tests should not override user changed src code without user permission

#### Guidelines

1. **Prefer to change the tests rather than app code**
2. **If app code changes are needed ask the user first**

### Rule: Refrain from import inside functions

#### Guidelines

1. **Prefer no import inside functions**: Do not add import inside functions if possible
2. **Only add if no other choice**: If you run into circular import problems. Although this is likely a sign of badly structure code/project folders and that might be better to address

### Rule: Minimalist Package Entrypoints

Directly address the "Redundant Import" anti-pattern in **init**.py files.

#### Guidelines

1. **No Manual Promotion**: Do not "promote" classes or functions from submodules into `__init__.py` unless it is a strictly required public-facing SDK.
2. **Prefer Direct Imports**: Encourage the use of `from ai.hooks.base import HookConfig` instead of `from ai.hooks import HookConfig`.
3. **Implicit Over Explicit**: If a package is for internal use, `__init__.py` must remain empty or contain only a docstring.
4. **Delete all**: Avoid `__all__` lists in `__init__.py` unless the package is a distributed library where namespace pollution is a high risk.

#### Refactoring Trigger

If you see an `__init__.py` that simply re-exports symbols from its own submodules (e.g., `from .base import X` + `__all__ = ["X"]`):

- **Action**: Delete the imports and the `__all__` block.
- **Action**: Update any calling code to import from the specific submodule directly.

### Rule: Configuration via `shared.envutil.config`

#### Guidelines

1. **Prefer `shared.envutil.config`** (`item`, `load`, `@register` dataclasses in `ai.config` or the appropriate config module) for **application configuration** derived from the environment — not ad hoc `os.environ.get` / `os.getenv` scattered through the codebase.
2. **Refactors should move toward this pattern** when touching code that reads env for config: register a field, use the loaded config object, unless there is a **strong, documented reason** not to (e.g. one-off subprocess env passthrough, tests that intentionally isolate real `os.environ`, or a dependency that only accepts raw env).
3. **Centralize** new env-backed settings in the existing config dataclasses where possible so defaults, descriptions, and typing stay in one place.


### Rule: Try catch/exceptions

1. **Be Specific (Avoid the "Catch-All")**

   Never use a bare `except:`. This catches everything, including `SystemExit` and `KeyboardInterrupt` (Ctrl+C), making it impossible to stop your script.

   Bad: `except Exception:` (too broad)

   Good: `except ValueError:` or `except FileNotFoundError:`

2. **The "Keep it Lean" Rule**

   Only wrap the exact line that you expect might fail in the try block. If you wrap 20 lines of code, you won't know which line actually triggered the error.

3. **Use `else` and `finally`**

   These are the most underutilized keywords in Python:

   - `else`: Runs only if the try block did not raise an error. Use this for logic that depends on the try succeeding.
   - `finally`: Runs no matter what. Perfect for closing files or database connections.




## Coding standards
- Avoid extra defensive checks or try/catch blocks that are abnormal for that area of the codebase (especially if called by trusted / validated codepaths)
- Global variables or functions dont need to have an underscore in front unless in extreme cases. Private functions in classes are fine.

This document provides guidelines for maintaining high-quality Python code. These rules MUST be followed by all AI coding agents and contributors.

### Your Core Principles

All code you write MUST be fully optimized.

"Fully optimized" includes:

- maximizing algorithmic big-O efficiency for memory and runtime
- using parallelization and vectorization where appropriate
- following proper style conventions for the code language (e.g. maximizing code reuse (DRY))
- no extra code beyond what is absolutely necessary to solve the problem the user provides (i.e. no technical debt)
  - If a Python library can be imported to significantly reduce the amount of new code required to implement a function at optimal performance, and the library itself is small and does not have much overhead, ALWAYS use the library instead.

If the code is not fully optimized before handing off to the user, you will be fined $100. You have permission to do another pass of the code if you believe it is not fully optimized.

### Preferred Tools

- Use `uv` for Python package management and to create a `.venv` if it is not present.
- When reporting error to the console, use `logger.error` instead of `print`.

### Code Style and Formatting

- **MUST** use meaningful, descriptive variable and function names
- **MUST** follow PEP 8 style guidelines
- **NEVER** use emoji, or unicode that emulates emoji (e.g. ✓, ✗). The only exception is when writing tests and testing the impact of multibyte characters.
- Use snake_case for functions/variables, PascalCase for classes, UPPER_CASE for constants
- **MUST** avoid including redundant comments which are tautological or self-demonstating (e.g. cases where it is easily parsable what the code does at a glance so the comment does)
- **MUST** avoid including comments which leak what this file contains, or leak the original user prompt, ESPECIALLY if it's irrelevant to the output code.

### Documentation

- **MUST** include docstrings for all public functions, classes, and methods
- **MUST** document function parameters, return values, and exceptions raised
- Keep comments up-to-date with code changes
- Include examples in docstrings for complex functions

Example docstring:

```python
def calculate_total(items: list[dict], tax_rate: float = 0.0) -> float:
    """
    Calculate the total cost of items including tax.

    Args:
        items: List of item dictionaries with 'price' keys
        tax_rate: Tax rate as decimal (e.g., 0.08 for 8%)

    Returns:
        Total cost including tax

    Raises:
        ValueError: If items is empty or tax_rate is negative
    """
```

### Type Hints

- **MUST** use type hints for all function signatures (parameters and return values)
- **NEVER** use `Any` type unless absolutely necessary
- **MUST** run mypy and resolve all type errors
- Use `Optional[T]` or `T | None` for nullable types

### Error Handling

- **NEVER** silently swallow exceptions without logging
- **MUST** never use bare `except:` clauses
- **MUST** catch specific exceptions rather than broad exception types
- **MUST** use context managers (`with` statements) for resource cleanup
- Provide meaningful error messages

### Function Design

- **MUST** keep functions focused on a single responsibility
- **NEVER** use mutable objects (lists, dicts) as default argument values
- Limit function parameters to 5 or fewer
- Return early to reduce nesting

### Class Design

- **MUST** keep classes focused on a single responsibility
- **MUST** keep `__init__` simple; avoid complex logic
- Use dataclasses for simple data containers
- Prefer composition over inheritance
- Avoid creating additional class functions if they are not necessary
- Use `@property` for computed attributes

### Testing

- **MUST** write unit tests for all new functions and classes
- **MUST** mock external dependencies (APIs, databases, file systems)
- **MUST** use pytest as the testing framework
- **NEVER** run tests you generate without first saving them as their own discrete file
- **NEVER** delete files created as a part of testing.
- Ensure the folder used for test outputs is present in `.gitignore`
- Follow the Arrange-Act-Assert pattern
- Do not commit commented-out tests

### Imports and Dependencies

- **MUST** avoid wildcard imports (`from module import *`)
- **MUST** document dependencies in `pyproject.toml`
- Use `uv` for fast package management and dependency resolution
- Organize imports: standard library, third-party, local imports
- Use `isort` to automate import formatting

### Python Best Practices

- **NEVER** use mutable default arguments
- **MUST** use context managers (`with` statement) for file/resource management
- **MUST** use `is` for comparing with `None`, `True`, `False`
- **MUST** use f-strings for string formatting
- Use list comprehensions and generator expressions
- Use `enumerate()` instead of manual counter variables
- **MUST** for Python docstrings pad delimiters — `""" text. """`, not `"""text."""`.

---

**Remember:** Prioritize clarity and maintainability over cleverness. This is your core directive.



