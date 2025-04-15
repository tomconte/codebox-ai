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

logger = logging.getLogger(__name__)


class MCPCodeService:
    """MCP interface to CodeBox-AI execution service"""

    def __init__(self):
        self.code_service = CodeExecutionService()
        self.active_sessions: Dict[str, Dict[str, Any]] = {}

    async def _wait_for_execution(self, request_id: str, timeout: int = 60) -> Dict[str, Any]:
        """Wait for code execution to complete and return results"""
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            if request_id in self.code_service.results:
                return self.code_service.results[request_id]
            await asyncio.sleep(0.5)

        return {"status": "timeout", "error": "Execution timed out", "output": []}


@asynccontextmanager
async def codebox_lifespan(server: FastMCP) -> AsyncIterator[None]:
    """Lifespan manager for the MCP server"""
    logger.info("Starting CodeBox-AI MCP server")
    yield
    logger.info("Shutting down CodeBox-AI MCP server")


def create_mcp_server(name: str = "CodeBox-AI") -> FastMCP:
    """Create and configure the MCP server"""
    mcp_service = MCPCodeService()
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
            session_id = None  # TODO: Implement session management
            if not session_id:
                session_id = await mcp_service.code_service.create_session(dependencies)
            request_data = {"code": code, "session_id": session_id, "dependencies": dependencies or []}
            request_id = await mcp_service.code_service.create_execution_request(request_data)
            await mcp_service.code_service.execute_code(request_id)
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
