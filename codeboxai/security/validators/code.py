import ast
import logging
import re
from dataclasses import dataclass, field
from functools import wraps
from typing import Callable, Dict, List, Optional, Pattern, Set, Tuple

logger = logging.getLogger(__name__)

blocked_packages = {
    # Security Sensitive
    "crypto",  # Cryptographic operations
    "pycrypto",  # Cryptographic operations
    "cryptography",  # Cryptographic operations
    "paramiko",  # SSH protocol
    "fabric",  # SSH automation
    "ansible",  # System automation
    "salt",  # System automation
    "puppet",  # System automation
    # System Access
    "psutil",  # System and process utilities
    "pywin32",  # Windows system access
    "winreg",  # Windows registry access
    "win32com",  # Windows COM interface
    "win32api",  # Windows API access
    # Code Execution & Compilation
    "pyinstaller",  # Creates executables
    "py2exe",  # Creates executables
    "cx_Freeze",  # Creates executables
    "distutils",  # Package distribution
    "pycdlib",  # ISO image manipulation
    # Network & Server
    "django",  # Web framework
    "flask",  # Web framework
    "fastapi",  # Web framework
    "tornado",  # Web framework
    "twisted",  # Network framework
    "socketserver",  # Network servers
    "ftplib",  # FTP protocol
    "smtplib",  # Email sending
    # System Shell & Commands
    "sh",  # Shell commands
    "shellingham",  # Shell detection
    "pexpect",  # Process control
    "pyshell",  # Shell interface
    # Low-level System Access
    "ctypes",  # C-compatible data types
    "cffi",  # Foreign function interface
    "mmap",  # Memory mapping
    # Remote Code & Debuggers
    "code",  # Code module
    "pdb",  # Python debugger
    "rpdb",  # Remote debugger
    "ipdb",  # IPython debugger
    "pyrasite",  # Process injection
    # Other Potentially Dangerous
    "docker",  # Docker control
    "kubernetes",  # Kubernetes control
    "boto3",  # AWS SDK
    "azure",  # Azure SDK
    "google-cloud",  # GCP SDK
}


@dataclass
class ValidationRule:
    name: str
    description: str
    enabled: bool = True
    validation_fn: Optional[Callable[[str], Tuple[bool, Optional[str]]]] = None


@dataclass
class PackageValidationRule(ValidationRule):
    allowed_packages: Set[str] = field(default_factory=set)
    blocked_packages: Set[str] = field(default_factory=set)
    allowed_versions: Dict[str, Set[str]] = field(default_factory=dict)


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


def create_validator_with_disabled_rules(disabled_rules: Optional[List[str]] = None) -> "CodeValidator":
    """
    Factory function to create a new CodeValidator with specific rules disabled

    Args:
        disabled_rules: List of rule names to disable, or ["all"] to disable all validation

    Returns:
        A configured CodeValidator instance
    """
    validator = CodeValidator()

    if disabled_rules:
        if "all" in disabled_rules:
            # Disable all rules
            for rule in validator.rules:
                validator.disable_rule(rule.name)
        else:
            # Disable specific rules
            for rule_name in disabled_rules:
                validator.disable_rule(rule_name)

    return validator


class CodeValidator:
    """Validates Python code for security concerns while allowing Jupyter/IPython syntax"""

    def __init__(self):
        # Initialize base security rules
        self.forbidden_builtins: Set[str] = {
            "eval",
            "exec",
            "globals",
            "locals",
            "compile",
            "__import__",
        }

        self.forbidden_modules: Set[str] = {
            "sys",
            "subprocess",
            "multiprocessing",
            "socket",
            "pickle",
            "marshal",
            "shelve",
            "pty",
            "pdb",
        }

        self.forbidden_patterns: List[Pattern] = [
            re.compile(r"(?<![\!%])__\w+__"),
        ]

        self.jupyter_patterns: List[Pattern] = [
            re.compile(r"^\s*!.*$", re.MULTILINE),  # Shell commands
            re.compile(r"^\s*%.*$", re.MULTILINE),  # Line magic
            re.compile(r"^\s*%%.*$", re.MULTILINE),  # Cell magic
        ]

        self.allowed_shell_commands: Set[str] = {
            "pip",
            "conda",
            "jupyter",
            "python",
            "pytest",
            "black",
            "flake8",
            "mypy",
            "curl",
            "wget",
        }

        # Initialize validation rules
        self._initialize_rules()

    def _initialize_rules(self):
        """Initialize the validation rules"""
        self.rules: List[ValidationRule] = [
            ValidationRule(
                name="jupyter_commands",
                description="Validate Jupyter magic and shell commands",
                validation_fn=self._validate_jupyter_commands,
            ),
            ValidationRule(
                name="dangerous_builtins",
                description="Prevent use of dangerous built-in functions",
                validation_fn=self._validate_builtins,
            ),
            ValidationRule(
                name="dangerous_imports",
                description="Prevent importing of dangerous modules",
                validation_fn=self._validate_imports,
            ),
            ValidationRule(
                name="dangerous_patterns",
                description="Prevent dangerous code patterns",
                validation_fn=self._validate_patterns,
            ),
        ]

        # Add package validation rule
        self.rules.append(
            PackageValidationRule(
                name="package_installation",
                description="Validate package installation commands",
                validation_fn=self._validate_package_installation,
                allowed_packages=set(),  # Empty - allow all except blocked
                blocked_packages=blocked_packages,
                allowed_versions={
                    # Set minimum versions for security
                    "pillow": {">=9.0.0"},
                    "numpy": {">=1.22.2"},
                    "requests": {">=2.31.0"},
                    "pandas": {">=1.4.0"},
                    "tensorflow": {">=2.11.1"},
                    "torch": {">=1.13.1"},
                    "urllib3": {">=1.26.5"},
                    "scipy": {">=1.10.0"},
                },
            )
        )

        # Create a rules lookup for easy access
        self.rules_lookup: Dict[str, ValidationRule] = {rule.name: rule for rule in self.rules}

    def enable_rule(self, rule_name: str):
        """Enable a specific validation rule"""
        if rule_name in self.rules_lookup:
            self.rules_lookup[rule_name].enabled = True
            logger.debug(f"Enabled validation rule: {rule_name}")

    def disable_rule(self, rule_name: str):
        """Disable a specific validation rule"""
        if rule_name in self.rules_lookup:
            self.rules_lookup[rule_name].enabled = False
            logger.debug(f"Disabled validation rule: {rule_name}")
        else:
            logger.warning(f"Attempted to disable unknown validation rule: {rule_name}")

    def _validate_package_installation(self, code: str) -> Tuple[bool, Optional[str]]:
        """Validates package installation commands"""
        package_rule = self.rules_lookup.get("package_installation")
        if not isinstance(package_rule, PackageValidationRule):
            return True, None

        # Regular expressions to match different installation patterns
        pip_patterns = [
            r"!(?:python\s+-m\s+)?pip(?:3)?\s+install\s+([-\w\d\s,\.=<>]+)",
            r"!conda\s+install\s+([-\w\d\s,\.=<>]+)",
        ]

        for pattern in pip_patterns:
            matches = re.finditer(pattern, code, re.MULTILINE)
            for match in matches:
                packages_str = match.group(1)
                packages = [p.strip() for p in packages_str.split() if p.strip()]

                for package in packages:
                    # Split package name and version specifier
                    parts = re.split(r"(>=|<=|==|>|<|!=)", package)
                    package_name = parts[0]
                    version_spec = "".join(parts[1:]) if len(parts) > 1 else None

                    # Check if package is blocked
                    if package_name.lower() in package_rule.blocked_packages:
                        return False, f"Package {package_name} is blocked for security reasons"

                    # If we have an allowlist and package isn't in it
                    if package_rule.allowed_packages and package_name not in package_rule.allowed_packages:
                        return False, f"Package {package_name} is not in the allowed packages list"

                    # Check version constraints if they exist for this package
                    if version_spec and package_name in package_rule.allowed_versions:
                        from packaging import specifiers, version

                        try:
                            allowed = specifiers.SpecifierSet(",".join(package_rule.allowed_versions[package_name]))

                            # For exact versions, directly check if they satisfy the allowed specifier
                            if "==" in version_spec:
                                ver = version.Version(version_spec.split("==")[1])
                                if not allowed.contains(ver):
                                    return (
                                        False,
                                        f"Version {ver} of {package_name} is not allowed. Must satisfy: {allowed}",
                                    )
                            else:
                                # For range specifications, check against minimum allowed version
                                requested = specifiers.SpecifierSet(version_spec)
                                min_allowed = None
                                for spec in allowed:
                                    if ">=" in str(spec):
                                        min_allowed = str(spec).replace(">=", "")
                                        break

                                if min_allowed:
                                    min_ver = version.Version(min_allowed)
                                    test_ver = version.Version(str(min_ver.major) + "." + str(min_ver.minor))
                                    if test_ver < min_ver and requested.contains(test_ver):
                                        return (
                                            False,
                                            f"Version {version_spec} of {package_name} would allow "
                                            f"versions below minimum required ({min_allowed}). "
                                            f"Must satisfy: {allowed}",
                                        )

                        except Exception as e:
                            return False, f"Invalid version specification for {package_name}: {str(e)}"

        return True, None

    def _validate_jupyter_commands(self, code: str) -> Tuple[bool, Optional[str]]:
        """Validates Jupyter shell commands for safety"""
        shell_lines = [line.strip() for line in code.split("\n") if line.strip().startswith("!")]

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
                    base_module = name.name.split(".")[0]
                    if base_module in self.forbidden_modules:
                        return False, f"Forbidden import: {name.name}"

            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] in self.forbidden_modules:
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

        for line in code.split("\n"):
            is_jupyter = any(pattern.match(line.strip()) for pattern in self.jupyter_patterns)
            if is_jupyter:
                jupyter_commands.append(line)
            else:
                python_code.append(line)

        # Run enabled validation rules
        for rule in self.rules:
            if rule.enabled:
                # Run Jupyter command validation on full code
                if rule.name == "jupyter_commands" or rule.name == "package_installation":
                    is_valid, message = rule.validation_fn(code)
                # Run other validations only on Python code parts
                else:
                    is_valid, message = rule.validation_fn("\n".join(python_code))

                if not is_valid and message:
                    failures.append(message)

        if failures:
            return False, "; ".join(failures)
        return True, "Code validation passed"
