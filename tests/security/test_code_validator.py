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


def test_package_version_validation(validator):
    test_cases = [
        # Basic version tests
        ("!pip install pillow>=9.0.0", True, "Minimum allowed version should pass"),
        ("!pip install pillow==8.0.0", False, "Version below minimum should fail"),
        ("!pip install pillow==9.0.0", True, "Exact minimum version should pass"),
        ("!pip install pillow==9.2.0", True, "Version above minimum should pass"),

        # Complex version specs
        ("!pip install pillow>9.0.0,<10.0.0",
         True, "Valid version range should pass"),

        # Multiple packages
        ("!pip install pillow>=9.0.0 numpy>=1.22.2",
         True, "Multiple valid packages should pass"),
        ("!pip install pillow>=9.0.0 numpy==1.20.0",
         False, "One invalid version should fail"),

        # Different pip install syntaxes
        ("!python -m pip install pillow>=9.0.0",
         True, "python -m pip syntax should work"),

        # Blocked packages
        ("!pip install crypto", False, "Blocked package should fail"),
        ("!pip install crypto==1.0.0", False,
         "Blocked package with version should fail"),
        ("!pip install pillow>=9.0.0 crypto", False,
         "Valid package with blocked package should fail"),

        # Package without version
        ("!pip install requests", True,
         "Package without version specification should pass"),
        ("!pip install pillow", True,
         "Package without version should pass when has allowed versions"),

        # Conda syntax
        ("!conda install pillow>=9.0.0", True, "Conda syntax should work"),
        ("!conda install pillow==8.0.0", False,
         "Conda syntax should enforce versions"),

        # Edge cases
        ("!pip install pillow>=9.0.0 # some comment",
         True, "Comments should be handled"),
        ("!pip install --upgrade pillow>=9.0.0",
         True, "Pip flags should be handled"),
        ("!pip install -U pillow>=9.0.0", True,
         "Short pip flags should be handled"),
        ("!pip install", True, "Empty pip install should pass"),
        ("print('!pip install pillow')", True,
         "Pip command in string should pass"),

        # Invalid syntax
        ("!pip install pillow>=invalid", False,
         "Invalid version syntax should fail"),
    ]

    for code, should_pass, message in test_cases:
        is_valid, error_msg = validator.validate_code(code)
        assert is_valid == should_pass, f"{message}: {
            code} - {'Failed' if should_pass else 'Passed'} with error: {error_msg}"


def test_multiple_validation_rules(validator):
    """Test interaction between package validation and other security rules"""
    test_cases = [
        # Package validation with other security rules
        ("""
!pip install pillow>=9.0.0
import numpy as np
print('Hello')
        """, True, "Valid package with safe code should pass"),

        ("""
!pip install pillow>=9.0.0
import sys  # forbidden import
        """, False, "Valid package with forbidden import should fail"),

        ("""
!pip install crypto  # blocked package
import numpy as np
        """, False, "Blocked package with safe import should fail"),
    ]

    for code, should_pass, message in test_cases:
        is_valid, error_msg = validator.validate_code(code)
        assert is_valid == should_pass, f"{message}: {
            'Failed' if should_pass else 'Passed'} with error: {error_msg}"


def test_package_name_variants(validator):
    """Test various package name formats and variants"""
    test_cases = [
        ("!pip install scikit-learn>=1.0.0",
         True, "Package with hyphen should work"),
        ("!pip install python_dateutil>=2.0.0", True,
         "Package with underscore should work"),
        ("!pip install pillow[extra]>=9.0.0",
         True, "Package with extras should work"),
        ("!pip install Flask", False,
         "Blocked package with capital letters should fail"),
        ("!pip install PILLOW>=9.0.0", True,
         "Package name should be case insensitive"),
    ]

    for code, should_pass, message in test_cases:
        is_valid, error_msg = validator.validate_code(code)
        assert is_valid == should_pass, f"{message}: {
            'Failed' if should_pass else 'Passed'} with error: {error_msg}"
