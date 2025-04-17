import atexit
import logging
from typing import Any, Dict

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from codeboxai.models import (
    ExecutionRequest,
    ExecutionResponse,
    SessionRequest,
    SessionResponse,
    StatusResponse,
)
from codeboxai.service import CodeExecutionService

logger = logging.getLogger(__name__)

code_service = None

app = FastAPI(
    title="CodeBox-AI", description="Secure Python code execution service with IPython kernel", version="0.1.0"
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Extract the custom message from the Pydantic error
    error_message = str(exc.errors()[0].get("ctx", {}).get("error", str(exc)))
    return JSONResponse(
        status_code=400,  # Using 400 instead of 422 as it's more appropriate for validation
        content={"status": "error", "message": error_message},
    )


@app.post("/sessions")
async def create_session(request: SessionRequest):
    """Create a new session with optional dependencies"""
    try:
        session_id = await code_service.create_session(request.dependencies, request.execution_options)
        return SessionResponse(
            session_id=session_id, status="created", created_at=code_service.sessions[session_id]["created_at"]
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/execute")
async def create_execution(request: ExecutionRequest, background_tasks: BackgroundTasks):
    """Execute code in a session"""
    try:
        request_id = await code_service.create_execution_request(request)
        background_tasks.add_task(code_service.execute_code, request_id)

        return ExecutionResponse(
            request_id=request_id, status="created", created_at=code_service.requests[request_id]["created_at"]
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/execute/{request_id}/status")
async def get_execution_status(request_id: str) -> StatusResponse:
    """Get the status of a code execution request"""
    request = code_service.requests.get(request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    result = code_service.results.get(request_id, {})

    return StatusResponse(
        request_id=request_id,
        status=result.get("status", request["status"]),
        created_at=request["created_at"],
        completed_at=result.get("completed_at"),
    )


@app.get("/execute/{request_id}/results")
async def get_execution_results(request_id: str) -> Dict[str, Any]:
    """Get the results of a code execution request"""
    result = code_service.results.get(request_id)
    if not result:
        raise HTTPException(status_code=404, detail="Results not available")

    return {
        "status": result["status"],
        "output": result["output"],
        "error": result.get("error"),
        "files": result.get("files", []),
        "completed_at": result["completed_at"],
    }


@app.delete("/sessions/{session_id}")
async def cleanup_session(session_id: str):
    """Cleanup a session and its resources"""
    if session_id in code_service.sessions:
        code_service.cleanup_session(session_id)
        return {"status": "cleaned up"}
    raise HTTPException(status_code=404, detail="Session not found")


# Configure logging on startup
@app.on_event("startup")
async def configure_logging():
    # Get uvicorn logger
    uvicorn_logger = logging.getLogger("uvicorn")
    # Configure logging
    root_logger = logging.getLogger()
    root_logger.addHandler(uvicorn_logger.handlers[0])
    root_logger.setLevel(logging.INFO)

    # Initialize code execution service
    global code_service
    code_service = CodeExecutionService()

    logger.info("CodeBox-AI service started")


# Cleanup on shutdown
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup all sessions on shutdown"""
    for session_id in list(code_service.sessions.keys()):
        code_service.cleanup_session(session_id)


# Also register cleanup with atexit for safety
atexit.register(lambda: [code_service.cleanup_session(rid) for rid in list(code_service.sessions.keys())])

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
