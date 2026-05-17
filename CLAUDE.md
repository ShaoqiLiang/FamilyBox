# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FamilyBox is a Python project in early development. It uses `uv` as the package manager and targets Python 3.14+.

## Common Commands

```bash
# Install dependencies
uv sync

# Run the application
uv run main.py

# Run tests
uv run pytest

# Run a single test
uv run pytest tests/test_file.py::test_name

# Type checking
uv run mypy .

# Linting and formatting
uv run ruff check .
uv run ruff format .
```

## Tooling

- **Package manager**: uv (lockfile: `uv.lock`)
- **Python version**: 3.14 (pinned in `.python-version`)
- **Linter/formatter**: ruff
- **Type checker**: mypy
- **Test framework**: pytest
