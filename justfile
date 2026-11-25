# Routine commands for mailmd. Run `just` to list them.
# Recipes use bash syntax; on Windows they run in Git Bash (adjust the path below if Git lives elsewhere).

set windows-shell := ["C:/Program Files/Git/bin/bash.exe", "-cu"]

# Pass recipe arguments through as "$@" so file names with spaces survive intact
set positional-arguments := true

# List the recipes
default:
    @just --list --unsorted

# Install dependencies into the project environment
sync:
    uv sync

# Run the tests; extra arguments go to pytest (e.g. `just test -k naming`)
test *args:
    uv run pytest "$@"

# Lint and check formatting without changing files
lint:
    uv run ruff check .
    uv run ruff format --check .

# Fix lint issues that ruff can fix, then format
fmt:
    uv run ruff check --fix .
    uv run ruff format .

# Type-check the package and tools
types:
    uv run ty check src tools

# Scan every tracked file for real email details (uses .leakcheck.local if present)
leakcheck:
    git ls-files -z | xargs -0 uv run python tools/leakcheck.py

# Everything that must pass before pushing
check: lint types test leakcheck

# Install the prek pre-commit and commit-msg hooks (once per clone)
hooks:
    uvx prek install

# Run the CLI from the working tree (e.g. `just convert samples/case/thread.eml -o out`)
convert *args:
    uv run mailmd convert "$@"

# Install mailmd as a global command from this checkout
install:
    uv tool install --force .
