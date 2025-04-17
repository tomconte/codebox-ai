import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from codeboxai.security.validators.code import CodeValidator


class MountPoint(BaseModel):
    host_path: str  # Path on host machine
    container_path: str  # Path in container
    read_only: bool = Field(default=True)  # Default to read-only for security

    @field_validator("host_path")
    @classmethod
    def validate_host_path(cls, path: str) -> str:
        # Ensure path exists
        if not Path(path).exists():
            raise ValueError(f"Host path does not exist: {path}")

        # Basic security validation - restrict certain system directories
        restricted_paths = ["/etc", "/var", "/bin", "/sbin", "/usr/bin", "/usr/sbin", "/boot", "/dev", "/proc", "/sys"]
        path_obj = Path(os.path.abspath(path)).resolve()

        for restricted in restricted_paths:
            if str(path_obj).startswith(restricted):
                raise ValueError(f"Access to {restricted} is restricted")

        return str(path_obj)

    @field_validator("container_path")
    @classmethod
    def validate_container_path(cls, path: str) -> str:
        # Container path should be absolute
        if not path.startswith("/"):
            raise ValueError("Container path must be absolute")

        # Restrict mounting to sensitive container locations
        restricted_paths = ["/etc", "/var/run", "/proc", "/sys"]
        for restricted in restricted_paths:
            if path.startswith(restricted):
                raise ValueError(f"Cannot mount to {restricted} in container")

        return path


class ExecutionOptions(BaseModel):
    timeout: int = Field(default=300, ge=1, le=600)
    memory_limit: str = Field(default="2G")
    cpu_limit: str = Field(default="1")
    environment_variables: Optional[Dict[str, str]] = None
    mount_points: Optional[List[MountPoint]] = Field(default_factory=list)


class ExecutionRequest(BaseModel):
    code: str = Field(max_length=100000)
    language: str = Field(default="python", pattern="^python$")
    dependencies: Optional[List[str]] = Field(default_factory=list)
    execution_options: ExecutionOptions = Field(default_factory=ExecutionOptions)
    session_id: Optional[str] = None

    @field_validator("code")
    @classmethod
    def validate_code(cls, code: str) -> str:
        validator = CodeValidator()
        is_valid, message = validator.validate_code(code)
        if not is_valid:
            raise ValueError(message)
        return code


class SessionRequest(BaseModel):
    dependencies: Optional[List[str]] = Field(default_factory=list)
    execution_options: ExecutionOptions = Field(default_factory=ExecutionOptions)


class ExecutionResponse(BaseModel):
    request_id: str
    status: str
    created_at: str


class StatusResponse(BaseModel):
    request_id: str
    status: str
    created_at: str
    completed_at: Optional[str] = None


class ResultResponse(BaseModel):
    status: str
    output: List[Dict[str, Any]]
    error: Optional[Dict[str, Any]]
    files: List[str]
    completed_at: str


class SessionResponse(BaseModel):
    session_id: str
    status: str
    created_at: str
