import pytest

from codeboxai.security.validators.code import CodeValidator


@pytest.fixture
def validator():
    return CodeValidator()


def test_enable_disable_rules(validator):
    # Disable dangerous imports rule
    validator.disable_rule("dangerous_imports")

    # This should now pass even though it imports os
    code = "import os"
    is_valid, message = validator.validate_code(code)
    assert is_valid

    # Re-enable the rule
    validator.enable_rule("dangerous_imports")

    # Now it should fail
    is_valid, message = validator.validate_code(code)
    assert not is_valid
    assert "Forbidden import" in message


def test_individual_rules(validator):
    # Test jupyter commands rule
    is_valid, message = validator.rules_lookup["jupyter_commands"].validation_fn(
        "!pip install numpy")
    assert is_valid

    is_valid, message = validator.rules_lookup["jupyter_commands"].validation_fn(
        "!rm -rf /")
    assert not is_valid

    # Test dangerous builtins rule
    is_valid, message = validator.rules_lookup["dangerous_builtins"].validation_fn(
        "print('hello')")
    assert is_valid

    is_valid, message = validator.rules_lookup["dangerous_builtins"].validation_fn(
        "eval('2+2')")
    assert not is_valid


def test_code_validator_dangerous_imports():
    validator = CodeValidator()
    code = "import os"
    is_valid, message = validator.validate_code(code)
    assert not is_valid
    assert "Forbidden import" in message


def test_code_validator_dangerous_functions():
    validator = CodeValidator()
    code = "eval('2 + 2')"
    is_valid, message = validator.validate_code(code)
    assert not is_valid
    assert "Forbidden function call" in message


def test_code_validator_safe_code():
    validator = CodeValidator()
    code = """
def add(a, b):
    return a + b
print(add(2, 2))
    """
    is_valid, message = validator.validate_code(code)
    assert is_valid
    assert "passed" in message


def test_code_validator_jupyter_shell_commands():
    validator = CodeValidator()
    test_cases = [
        ("!pip install numpy", True),  # Allowed
        ("!pip list", True),  # Allowed
        ("!rm -rf /", False),  # Not allowed
        ("!sudo apt-get update", False),  # Not allowed
    ]

    for code, should_pass in test_cases:
        is_valid, message = validator.validate_code(code)
        assert is_valid == should_pass, f"Failed for {code}: {message}"


def test_code_validator_jupyter_magic_commands():
    validator = CodeValidator()
    test_cases = [
        ("%matplotlib inline", True),
        ("%%time\nprint('hello')", True),
        ("%run script.py", True),
    ]

    for code, should_pass in test_cases:
        is_valid, message = validator.validate_code(code)
        assert is_valid == should_pass, f"Failed for {code}: {message}"


def test_code_validator_mixed_code():
    validator = CodeValidator()
    code = """
!pip install pandas
%matplotlib inline

import pandas as pd
df = pd.DataFrame({'a': [1, 2, 3]})
print(df)
    """
    is_valid, message = validator.validate_code(code)
    assert is_valid
    assert "passed" in message


def test_code_validator_dangerous_code_with_jupyter():
    validator = CodeValidator()
    code = """
!pip install pandas
import os  # This should still be caught
    """
    is_valid, message = validator.validate_code(code)
    assert not is_valid
    assert "Forbidden import" in message


def test_code_validator_shell_command_security():
    validator = CodeValidator()
    code = """
    !pip install pandas  # Allowed
    !rm -rf /  # Not allowed
    """
    is_valid, message = validator.validate_code(code)
    assert not is_valid
    assert "Shell command not allowed" in message
