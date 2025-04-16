"""
MCP Server implementation for CodeBox-AI.
This module provides the Model Context Protocol interface for CodeBox-AI.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, AsyncIterator

from mcp.server.fastmcp import FastMCP, Context
from mcp.types import ImageContent, TextContent

from codeboxai.service import CodeExecutionService
from codeboxai.models import ExecutionRequest, ExecutionOptions, MountPoint

logger = logging.getLogger(__name__)


class MCPCodeService:
    """MCP interface to CodeBox-AI execution service"""

    def __init__(self, mount_dirs: Optional[List[str]] = None):
        self.code_service = CodeExecutionService()
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.mount_dirs = mount_dirs or []

        if self.mount_dirs:
            logger.info(f"Configured server with {len(self.mount_dirs)} mounted directories: {self.mount_dirs}")

    async def _wait_for_execution(self, request_id: str, timeout: int = 60) -> Dict[str, Any]:
        """Wait for code execution to complete and return results"""
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            if request_id in self.code_service.results:
                return self.code_service.results[request_id]
            await asyncio.sleep(0.5)

        return {"status": "timeout", "error": "Execution timed out", "output": []}

    def _create_mount_points(self) -> List[MountPoint]:
        """Create MountPoint objects from configured directories"""
        mount_points = []
        for dir_path in self.mount_dirs:
            # Mount the directory at the same path in the container
            mount_points.append(
                MountPoint(
                    host_path=dir_path, container_path=dir_path, read_only=True  # Default to read-only for security
                )
            )
        return mount_points


@asynccontextmanager
async def codebox_lifespan(server: FastMCP) -> AsyncIterator[None]:
    """Lifespan manager for the MCP server"""
    logger.info("Starting CodeBox-AI MCP server")
    yield
    logger.info("Shutting down CodeBox-AI MCP server")


def create_mcp_server(name: str = "CodeBox-AI", mount_dirs: Optional[List[str]] = None) -> FastMCP:
    """Create and configure the MCP server

    Args:
        name: Name of the MCP server
        mount_dirs: List of directories to mount in the execution environment

    Returns:
        Configured FastMCP server instance
    """
    mcp_service = MCPCodeService(mount_dirs)
    mcp = FastMCP(name, lifespan=codebox_lifespan)

    @mcp.tool()
    async def execute_code(
        code: str, dependencies: Optional[List[str]] = None, ctx: Context = None
    ) -> List[TextContent | ImageContent]:
        """Execute Python code and return a list of TextContent or ImageContent objects

        Args:
            code: Python code to execute
            dependencies: Optional list of Python packages to install

        Returns:
            List of TextContent or ImageContent objects
        """
        from mcp import types

        contents: List[TextContent | ImageContent] = []
        try:
            # Create execution options with mount points if configured
            execution_options = None
            mount_points = mcp_service._create_mount_points()
            if mount_points:
                execution_options = ExecutionOptions(mount_points=mount_points)

            session_id = None  # TODO: Implement session management if/when supported by MCP
            if not session_id:
                session_id = await mcp_service.code_service.create_session(
                    dependencies=dependencies or [], execution_options=execution_options
                )

            # Create a new execution request
            exec_request = ExecutionRequest(session_id=session_id, code=code)
            request_id = await mcp_service.code_service.create_execution_request(exec_request)

            # Execute the code
            await mcp_service.code_service.execute_code(request_id)

            # Wait for execution to complete
            result = await mcp_service._wait_for_execution(request_id)

            # Add text outputs
            for output in result.get("output", []):
                if output["type"] == "stream" or output["type"] == "result":
                    contents.append(types.TextContent(type="text", text=output["content"]))

            # Add image outputs
            for file_data in result.get("files", []):
                contents.append(types.ImageContent(type="image", data=file_data, mimeType="image/png"))

            # Add error as text if present
            if result.get("error"):
                error_info = result["error"]
                if isinstance(error_info, dict):
                    error_text = f"Error: {error_info.get('ename', 'Unknown error')}\n{error_info.get('evalue', '')}\n"
                    if "traceback" in error_info:
                        error_text += "\n".join(error_info["traceback"])
                else:
                    error_text = f"Error: {error_info}"
                contents.append(types.TextContent(type="text", text=error_text))

            if not contents:
                contents.append(types.TextContent(type="text", text="No output."))

            return contents
        except Exception as e:
            logger.error(f"Error executing code: {e}")
            from mcp import types

            return [types.TextContent(type="text", text=f"Error: {str(e)}")]

        finally:
            # TODO: Implement session management; in the meantime, delete session
            if session_id:
                mcp_service.code_service.cleanup_session(session_id)

    @mcp.resource("session://{session_id}")
    async def get_session_info(session_id: str) -> str:
        """Get information about a specific code execution session"""
        if session_id in mcp_service.code_service.sessions:
            session = mcp_service.code_service.sessions[session_id]
            return (
                f"Session ID: {session_id}\n"
                f"Created: {session['created_at']}\n"
                f"Last Used: {session['last_used']}\n"
                f"Dependencies: {', '.join(session['dependencies']) if session['dependencies'] else 'None'}"
            )
        return f"Session {session_id} not found"

    @mcp.resource("sessions://")
    async def list_sessions() -> str:
        """List all active code execution sessions"""
        if not mcp_service.code_service.sessions:
            return "No active sessions"

        result = "Active Sessions:\n\n"
        for session_id, session in mcp_service.code_service.sessions.items():
            result += (
                f"Session ID: {session_id}\n"
                f"Created: {session['created_at']}\n"
                f"Last Used: {session['last_used']}\n"
                f"Dependencies: {', '.join(session['dependencies']) if session['dependencies'] else 'None'}\n\n"
            )
        return result

    return mcp
