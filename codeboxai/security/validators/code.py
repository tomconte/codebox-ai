from typing import Tuple, Set, List, Pattern, Callable, Optional, Dict
import re
import ast
from dataclasses import dataclass
import logging
from functools import wraps

logger = logging.getLogger(__name__)


@dataclass
class ValidationRule:
    name: str
    description: str
    enabled: bool = True
    validation_fn: Optional[Callable[[str], Tuple[bool, Optional[str]]]] = None


def ast_rule(f: Callable) -> Callable:
    """Decorator to handle AST parsing for rules that need it"""
    @wraps(f)
    def wrapper(self, code: str) -> Tuple[bool, Optional[str]]:
        try:
            tree = ast.parse(code)
            return f(self, tree)
        except SyntaxError as e:
            return False, f"Invalid Python syntax: {str(e)}"
    return wrapper


class CodeValidator:
    """Validates Python code for security concerns while allowing Jupyter/IPython syntax"""

    def __init__(self):
        # Initialize base security rules
        self.forbidden_builtins: Set[str] = {
            'eval', 'exec', 'globals', 'locals', 'compile',
            '__import__',
        }

        self.forbidden_modules: Set[str] = {
            'sys', 'subprocess', 'multiprocessing', 'socket',
            'pickle', 'marshal', 'shelve', 'pty', 'pdb'
        }

        self.forbidden_patterns: List[Pattern] = [
            re.compile(r'(?<![\!%])__\w+__'),
        ]

        self.jupyter_patterns: List[Pattern] = [
            re.compile(r'^\s*!.*$', re.MULTILINE),  # Shell commands
            re.compile(r'^\s*%.*$', re.MULTILINE),  # Line magic
            re.compile(r'^\s*%%.*$', re.MULTILINE),  # Cell magic
        ]

        self.allowed_shell_commands: Set[str] = {
            'pip', 'conda', 'jupyter', 'python',
            'pytest', 'black', 'flake8', 'mypy',
            'curl', 'wget',
        }

        # Initialize validation rules
        self._initialize_rules()

    def _initialize_rules(self):
        """Initialize the validation rules"""
        self.rules: List[ValidationRule] = [
            ValidationRule(
                name="jupyter_commands",
                description="Validate Jupyter magic and shell commands",
                validation_fn=self._validate_jupyter_commands
            ),
            ValidationRule(
                name="dangerous_builtins",
                description="Prevent use of dangerous built-in functions",
                validation_fn=self._validate_builtins
            ),
            ValidationRule(
                name="dangerous_imports",
                description="Prevent importing of dangerous modules",
                validation_fn=self._validate_imports
            ),
            ValidationRule(
                name="dangerous_patterns",
                description="Prevent dangerous code patterns",
                validation_fn=self._validate_patterns
            )
        ]

        # Create a rules lookup for easy access
        self.rules_lookup: Dict[str, ValidationRule] = {
            rule.name: rule for rule in self.rules
        }

    def enable_rule(self, rule_name: str):
        """Enable a specific validation rule"""
        if rule_name in self.rules_lookup:
            self.rules_lookup[rule_name].enabled = True

    def disable_rule(self, rule_name: str):
        """Disable a specific validation rule"""
        if rule_name in self.rules_lookup:
            self.rules_lookup[rule_name].enabled = False

    def _validate_jupyter_commands(self, code: str) -> Tuple[bool, Optional[str]]:
        """Validates Jupyter shell commands for safety"""
        shell_lines = [line.strip() for line in code.split('\n')
                       if line.strip().startswith('!')]

        for line in shell_lines:
            command = line[1:].strip().split()[0]  # Get first word after !
            if command not in self.allowed_shell_commands:
                return False, f"Shell command not allowed: {command}"

        return True, None

    @ast_rule
    def _validate_builtins(self, tree: ast.AST) -> Tuple[bool, Optional[str]]:
        """Validates that no dangerous builtins are used"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in self.forbidden_builtins:
                    return False, f"Forbidden function call: {node.func.id}"
        return True, None

    @ast_rule
    def _validate_imports(self, tree: ast.AST) -> Tuple[bool, Optional[str]]:
        """Validates that no dangerous imports are used"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    base_module = name.name.split('.')[0]
                    if base_module in self.forbidden_modules:
                        return False, f"Forbidden import: {name.name}"

            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split('.')[0] in self.forbidden_modules:
                    return False, f"Forbidden import: {node.module}"
        return True, None

    def _validate_patterns(self, code: str) -> Tuple[bool, Optional[str]]:
        """Validates that no dangerous patterns are found in the code"""
        for pattern in self.forbidden_patterns:
            if pattern.search(code):
                return False, f"Forbidden pattern found: {pattern.pattern}"
        return True, None

    def validate_code(self, code: str) -> Tuple[bool, str]:
        """
        Validates Python code for security concerns, allowing Jupyter syntax

        Args:
            code: The Python code to validate

        Returns:
            Tuple of (is_valid, message)
        """
        failures = []

        # Split code into Jupyter commands and Python code
        python_code = []
        jupyter_commands = []

        for line in code.split('\n'):
            is_jupyter = any(pattern.match(line.strip())
                             for pattern in self.jupyter_patterns)
            if is_jupyter:
                jupyter_commands.append(line)
            else:
                python_code.append(line)

        # Run enabled validation rules
        for rule in self.rules:
            if rule.enabled:
                # Run Jupyter command validation on full code
                if rule.name == "jupyter_commands":
                    is_valid, message = rule.validation_fn(code)
                # Run other validations only on Python code parts
                else:
                    is_valid, message = rule.validation_fn(
                        '\n'.join(python_code))

                if not is_valid and message:
                    failures.append(message)

        if failures:
            return False, "; ".join(failures)
        return True, "Code validation passed"
