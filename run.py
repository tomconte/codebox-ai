#!/usr/bin/env python
"""
Entry point for running CodeBox-AI servers.
Allows running the FastAPI server, MCP server, or both.
"""

import argparse
import logging
import os
import sys
import uvicorn

from codeboxai.main import app as fastapi_app
from codeboxai.mcp_server import create_mcp_server
from codeboxai.server import create_combined_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def run_fastapi(host: str = "0.0.0.0", port: int = 8000):
    """Run the FastAPI server"""
    logger.info(f"Starting FastAPI server on {host}:{port}")
    uvicorn.run(fastapi_app, host=host, port=port)


def run_mcp(host: str = "0.0.0.0", port: int = 8001):
    """Run the MCP server standalone"""
    logger.info(f"Starting MCP server on {host}:{port}")
    mcp = create_mcp_server("CodeBox-AI")
    uvicorn.run(mcp.sse_app(), host=host, port=port)


def run_combined(host: str = "0.0.0.0", port: int = 8000):
    """Run the combined FastAPI and MCP server"""
    logger.info(f"Starting combined server on {host}:{port}")
    app = create_combined_app()
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run CodeBox-AI servers")
    parser.add_argument(
        "--mode",
        choices=["fastapi", "mcp", "combined"],
        default="combined",
        help="Server mode to run (default: combined)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to (default: 8000)")
    parser.add_argument("--mcp-port", type=int, default=8001, help="Port for MCP when in separate mode (default: 8001)")

    args = parser.parse_args()

    # Set the Docker host environment variable if needed (for MacOS)
    if sys.platform == "darwin" and "DOCKER_HOST" not in os.environ:
        os.environ["DOCKER_HOST"] = "unix:///var/run/docker.sock"

    if args.mode == "fastapi":
        run_fastapi(args.host, args.port)
    elif args.mode == "mcp":
        run_mcp(args.host, args.mcp_port)
    else:  # combined
        run_combined(args.host, args.port)
