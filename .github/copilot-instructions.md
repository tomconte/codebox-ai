# CodeBox-AI Development Guide

This guide contains instructions for developing, building, and testing the CodeBox-AI project using uv's native commands.

## Build Commands

### Environment Setup
- Create virtual environment: `uv venv`
- Activate virtual environment: 
  - Unix/MacOS: `source .venv/bin/activate`
  - Windows: `.venv\Scripts\activate`
- Install all dependencies: `uv sync`
- Install with dev dependencies: `uv sync --extra dev`
- Install with specific extras: `uv sync --extra "dev docs"` or `uv sync --extra "dev docs examples"`

### Running the Application

#### Standard Server
```bash
uv run -m codeboxai.main
```

#### MCP Server Options
- Standalone MCP server (for Claude Desktop):
  ```bash
  uv run mcp dev mcp_server.py
  ```

- Register with Claude Desktop:
  ```bash
  uv run mcp install mcp_server.py --name "CodeBox-AI"
  ```

- Combined FastAPI + MCP server:
  ```bash
  uv run run.py
  ```

- MCP server only:
  ```bash
  uv run run.py --mode mcp
  ```

### Testing
- Run all tests: `uv run -m pytest`
- Run single test: `uv run -m pytest tests/path/to/test.py::test_function_name -v`
- Run tests with coverage: `uv run -m pytest --cov=codeboxai`
- Generate coverage report: `uv run -m pytest --cov=codeboxai --cov-report=html`

### Linting and Code Quality
- Run all code quality checks: `uv run pre-commit run --all-files`
- Individual checks:
  - Format code: `uv run -m black .`
  - Check imports: `uv run -m isort .`
  - Lint code: `uv run -m flake8`
  - Type checking: `uv run -m mypy .`

### Project Management
- Add a dependency: `uv add <package-name>`
- Remove a dependency: `uv remove <package-name>`
- Lock dependencies: `uv lock`
- View dependency tree: `uv tree`

### Building and Publishing
- Build package: `uv run -m build`
- Publish package: `uv publish`

## Code Style Guidelines

### Imports
- Group in order: stdlib, third-party, local
- Sort alphabetically within groups
- Use `isort` for automatic sorting

### Formatting
- Use `black` for code formatting with default settings (line length 120 as configured in pyproject.toml)
- Ensure consistent indentation (4 spaces)

### Type Annotations
- Use type hints for all function parameters and return values
- Use `mypy` for type checking

### Naming Conventions
- `snake_case` for functions and variables
- `CamelCase` for classes
- `UPPER_CASE` for constants

### Error Handling
- Use specific exceptions with meaningful error messages
- Log errors with appropriate level (error, warning, info)
- Handle exceptions at appropriate levels

### Docstrings
- Use Google-style docstrings with Args/Returns sections:
```python
def function(param1: str, param2: int) -> bool:
    """Short description.
    
    Longer description if needed.
    
    Args:
        param1: Description of first parameter
        param2: Description of second parameter
        
    Returns:
        Description of return value
        
    Raises:
        ExceptionType: When and why this exception is raised
    """
```

### Validation
- Use Pydantic validators for input validation
- Follow existing validation patterns

### Security
- Ensure all user inputs are properly validated and sanitized
- Use security best practices for Docker container isolation

### Testing
- Write pytest tests for all new functionality
- Aim for high test coverage, especially for security-critical code
- Write both unit tests and integration tests where appropriate

## Example Workflow

1. Create and activate environment:
```bash
uv venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
```

2. Install dependencies with development extras:
```bash
uv sync --extra "dev docs"
```

3. Run pre-commit to set up git hooks:
```bash
uv run pre-commit install
```

4. Make your code changes

5. Run tests to verify changes:
```bash
uv run -m pytest
```

6. Check code quality:
```bash
uv run -m black .
uv run -m isort .
uv run -m flake8
uv run -m mypy .
```

7. Run the server locally:
```bash
uv run -m codeboxai.main
```
