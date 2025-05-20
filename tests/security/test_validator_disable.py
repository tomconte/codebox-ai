from codeboxai.security.validators.code import create_validator_with_disabled_rules


def test_create_validator_with_disabled_rules():
    # Create validator with specific rule disabled
    validator = create_validator_with_disabled_rules(["dangerous_imports"])

    # This should now pass for the disabled rule
    code = "import sys"
    is_valid, message = validator.validate_code(code)
    assert is_valid

    # But should still fail for other rules
    code = "eval('2+2')"
    is_valid, message = validator.validate_code(code)
    assert not is_valid
    assert "Forbidden function call" in message


def test_create_validator_with_all_rules_disabled():
    # Create validator with all rules disabled
    validator = create_validator_with_disabled_rules(["all"])

    # This should pass any validation now
    code = """
import sys
eval('2+2')
!rm -rf /
"""
    is_valid, message = validator.validate_code(code)
    assert is_valid
    assert "passed" in message


def test_execution_request_with_disabled_validation(monkeypatch):
    from codeboxai.models import ExecutionRequest

    # Test with specific rule disabled
    request = ExecutionRequest(
        code="import sys\nprint('hello')", session_id="test-session", disable_validation=["dangerous_imports"]
    )

    # This should pass because we disabled the dangerous_imports rule
    assert "import sys" in request.code

    # Test with all validation disabled
    request = ExecutionRequest(
        code="import sys\neval('2+2')\n!rm -rf /", session_id="test-session", disable_validation=["all"]
    )

    # This should pass because we disabled all validation
    assert "import sys" in request.code
    assert "eval('2+2')" in request.code
    assert "!rm -rf /" in request.code
