from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class ExecutionOptions(BaseModel):
    timeout: int = Field(default=300, ge=1, le=600)
    memory_limit: str = Field(default="2G")
    cpu_limit: str = Field(default="1")
    environment_variables: Optional[Dict[str, str]] = None


class ExecutionRequest(BaseModel):
    code: str = Field(max_length=10000)
    language: str = Field(default="python", pattern="^python$")
    dependencies: Optional[List[str]] = Field(default_factory=list)
    execution_options: ExecutionOptions = Field(
        default_factory=ExecutionOptions)
    session_id: Optional[str] = None

    @field_validator('code')
    @classmethod
    def validate_code(cls, code: str) -> str:
        forbidden_keywords = ['import os',
                              'import sys', 'subprocess', '__import__']
        for keyword in forbidden_keywords:
            if keyword in code:
                raise ValueError(f"Potentially dangerous code: {
                                 keyword} not allowed")
        return code


class SessionRequest(BaseModel):
    dependencies: Optional[List[str]] = Field(default_factory=list)
    execution_options: ExecutionOptions = Field(
        default_factory=ExecutionOptions)


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
