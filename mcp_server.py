#!/usr/bin/env python
"""
Standalone MCP server for CodeBox-AI.
This file is designed to be used with MCP CLI tools.

Run with:
  mcp dev mcp_server.py
  or
  mcp install mcp_server.py
"""

import logging
import os
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Set Docker host environment for MacOS if needed
if sys.platform == "darwin" and "DOCKER_HOST" not in os.environ:
    docker_path = "/var/run/docker.sock"
    user_name = os.getenv("USER")
    if os.path.exists(f"/Users/{user_name}/.docker/run/docker.sock"):
        docker_path = f"/Users/{user_name}/.docker/run/docker.sock"
    os.environ["DOCKER_HOST"] = f"unix://{docker_path}"

from codeboxai.mcp_server import create_mcp_server

# Create the MCP server
mcp = create_mcp_server("CodeBox-AI")

# This will be run by the MCP CLI when using 'mcp dev' or 'mcp run'
if __name__ == "__main__":
    mcp.run()
