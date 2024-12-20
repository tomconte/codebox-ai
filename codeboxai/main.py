from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi_utils.tasks import repeat_every

from codeboxai.codebox import CodeBoxService, ExecutionRequest, Storage

app = FastAPI(
    title="CodeBox-AI",
    description="Secure Python code execution service with dependency management",
    version="0.1.0"
)

# Initialize the storage and code interpreter service
storage = Storage()
code_interpreter = CodeBoxService(storage)


@app.post("/execute")
async def create_execution(
    request: ExecutionRequest,
    background_tasks: BackgroundTasks
):
    try:
        request_id = await code_interpreter.create_execution_request(request)
        background_tasks.add_task(
            code_interpreter.execute_in_docker, request_id)

        return {
            "request_id": request_id,
            "status": "queued",
            "created_at": storage.requests[request_id]['created_at'],
            "dependencies": request.dependencies
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/execute/{request_id}/status")
async def get_execution_status(request_id: str):
    request = storage.requests.get(request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    result = storage.results.get(request_id, {})

    return {
        "request_id": request_id,
        "status": result.get('status', request['status']),
        "created_at": request['created_at'],
        "completed_at": result.get('completed_at'),
        "dependencies": request['dependencies']
    }


@app.get("/execute/{request_id}/results")
async def get_execution_results(request_id: str):
    result = storage.results.get(request_id)
    if not result:
        raise HTTPException(status_code=404, detail="Results not available")

    return {
        "status": result['status'],
        "stdout": result.get('stdout', ''),
        "stderr": result.get('stderr', ''),
        "files": result.get('files', []),
        "completed_at": result['completed_at'],
        "dependencies_installed": result.get('dependencies_installed', [])
    }


@app.get("/files/{request_id}/{filename}")
async def download_file(request_id: str, filename: str):
    file_path = code_interpreter.file_store.get_file_path(request_id, filename)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type='application/octet-stream'
    )


@app.get("/files/{request_id}")
async def list_files(request_id: str):
    files = code_interpreter.file_store.list_files(request_id)
    return {"files": files}


@app.on_event("startup")
@repeat_every(seconds=60 * 60)  # Run every hour
async def cleanup_old_files():
    code_interpreter.file_store.cleanup_old_files(max_age_hours=24)
