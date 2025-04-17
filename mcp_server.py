#!/usr/bin/env python
"""
Standalone MCP server for CodeBox-AI.
This file is designed to be used with MCP CLI tools.

Run with:
  mcp dev mcp_server.py
  or
  mcp install mcp_server.py

Optional arguments:
  --mount /path/to/directory1 /path/to/directory2 ... : Directories to mount in the execution environment
"""

import argparse
import logging
import os
import sys

from codeboxai.mcp_server import create_mcp_server

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Parse command line arguments
parser = argparse.ArgumentParser(description="CodeBox-AI MCP Server")
parser.add_argument("--mount", nargs="+", metavar="DIR", help="Directories to mount in the execution environment")
args, unknown_args = parser.parse_known_args()

# Set Docker host environment for MacOS if needed
if sys.platform == "darwin" and "DOCKER_HOST" not in os.environ:
    docker_path = "/var/run/docker.sock"
    user_name = os.getenv("USER")
    if os.path.exists(f"/Users/{user_name}/.docker/run/docker.sock"):
        docker_path = f"/Users/{user_name}/.docker/run/docker.sock"
    os.environ["DOCKER_HOST"] = f"unix://{docker_path}"

# Create the MCP server with mounted directories if specified
mount_dirs = args.mount or []
mcp = create_mcp_server("CodeBox-AI", mount_dirs=mount_dirs)

# This will be run by the MCP CLI when using 'mcp dev' or 'mcp run'
if __name__ == "__main__":
    logger.info(f"Starting server with mounted directories: {mount_dirs if mount_dirs else 'None'}")
    mcp.run()
