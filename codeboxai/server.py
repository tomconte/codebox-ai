"""
Combined server module that provides both FastAPI and MCP interfaces for CodeBox-AI.
"""

import logging

from starlette.applications import Starlette
from starlette.routing import Mount

from codeboxai.main import app as fastapi_app
from codeboxai.mcp_server import create_mcp_server

logger = logging.getLogger(__name__)


def create_combined_app() -> Starlette:
    """Create a combined application with both FastAPI and MCP interfaces"""
    # Create the MCP server
    mcp = create_mcp_server("CodeBox-AI")

    # Create a Starlette application that combines both
    combined_app = Starlette(
        routes=[
            # Mount the FastAPI app at the root path
            Mount("/", app=fastapi_app),
            # Mount the MCP SSE server at /mcp
            Mount("/mcp", app=mcp.sse_app()),
        ]
    )

    return combined_app


def run_server():
    """Run the combined server"""
    import uvicorn

    logger.info("Starting combined FastAPI and MCP server")
    app = create_combined_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run_server()
