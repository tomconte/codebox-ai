from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from codeboxai.models import ExecutionOptions, ExecutionRequest
from codeboxai.service import CodeExecutionService


@pytest.fixture
def mock_kernel_manager():
    with patch("codeboxai.service.KernelManager") as MockKM:
        yield MockKM


@pytest.mark.asyncio
async def test_create_session_success(mock_kernel_manager):
    service = CodeExecutionService()
    service.kernel_manager.start_kernel = MagicMock()
    service.kernel_manager.execute_code = MagicMock(return_value={"status": "ok", "outputs": [], "error": None})
    session_id = await service.create_session(["requests"], ExecutionOptions())
    assert session_id in service.sessions
    assert service.sessions[session_id]["dependencies"] == ["requests"]


@pytest.mark.asyncio
async def test_create_session_dependency_error(mock_kernel_manager):
    service = CodeExecutionService()
    service.kernel_manager.start_kernel = MagicMock()
    service.kernel_manager.execute_code = MagicMock(return_value={"status": "error", "error": "fail", "outputs": []})
    with pytest.raises(ValueError):
        await service.create_session(["badpackage"], ExecutionOptions())


@pytest.mark.asyncio
async def test_create_execution_request_creates_session(mock_kernel_manager):
    service = CodeExecutionService()
    service.create_session = AsyncMock(return_value="sid1")
    req = ExecutionRequest(code="print('hi')", session_id="sid1")
    request_id = await service.create_execution_request(req)
    assert request_id in service.requests
    assert service.requests[request_id]["session_id"] == "sid1"


@pytest.mark.asyncio
async def test_execute_code_success(mock_kernel_manager):
    service = CodeExecutionService()
    session_id = "sid1"
    request_id = "rid1"
    service.sessions[session_id] = {"last_used": "", "created_at": "", "dependencies": [], "execution_options": {}}
    service.requests[request_id] = {"session_id": session_id, "code": "print('hi')", "status": "initializing"}
    service.kernel_manager.execute_code = MagicMock(
        return_value={"status": "ok", "outputs": [{"type": "stream", "text": "hi\n"}], "error": None}
    )
    await service.execute_code(request_id)
    assert service.results[request_id]["status"] == "ok"
    assert service.results[request_id]["output"][0]["content"] == "hi\n"


@pytest.mark.asyncio
async def test_execute_code_error(mock_kernel_manager):
    service = CodeExecutionService()
    session_id = "sid1"
    request_id = "rid1"
    service.sessions[session_id] = {"last_used": "", "created_at": "", "dependencies": [], "execution_options": {}}
    service.requests[request_id] = {"session_id": session_id, "code": "raise Exception()", "status": "initializing"}
    service.kernel_manager.execute_code = MagicMock(side_effect=Exception("fail"))
    await service.execute_code(request_id)
    assert service.results[request_id]["status"] == "error"
    assert "fail" in service.results[request_id]["error"]


def test_cleanup_session(mock_kernel_manager):
    service = CodeExecutionService()
    session_id = "sid1"
    service.sessions[session_id] = {}
    service.kernel_manager.stop_kernel = MagicMock()
    service.cleanup_session(session_id)
    assert session_id not in service.sessions
    service.kernel_manager.stop_kernel.assert_called_once_with(session_id)
