# CodeBox-AI

A secure Python code execution service that provides a self-hosted alternative to OpenAI's Code Interpreter. Built with FastAPI and IPython kernels, it supports session-based code execution and integrates with LLM function calling. It also now supports the Model Context Protocol (MCP) for seamless integration with LLM applications.

## Features

- Session-based Python code execution in Docker containers
- IPython kernel for rich output support
- Dynamic package installation with security controls
  - Package allowlist/blocklist system
  - Version control for security vulnerabilities
  - Support for pip and conda installations
- State persistence between executions
- Support for plotting and visualization
- Code security validation
  - AST-based code analysis
  - Protection against dangerous imports and operations
  - Support for Jupyter magic commands and shell operations

## MCP Server (Model Context Protocol)

CodeBox-AI now supports the Model Context Protocol (MCP), allowing LLM applications (like Claude Desktop) to interact with your code execution service in a standardized way.

### Running the MCP Server

You can run the MCP server in several ways:

- **Standalone (for MCP clients or Claude Desktop):**
  ```bash
  uv run mcp dev mcp_server.py
  ```
  This starts the MCP server in development mode for local testing and debugging.

- **Register with Claude Desktop:**
  ```bash
  uv run mcp install mcp_server.py --name "CodeBox-AI"
  ```
  This will make your server available to Claude Desktop as a custom tool.

- **Combined FastAPI + MCP server:**
  ```bash
  python run.py
  ```
  This starts both the FastAPI API and the MCP server (MCP available at `/mcp`).

- **MCP server only:**
  ```bash
  python run.py --mode mcp
  ```

### MCP Features

- `execute_code`: Execute Python code and return results
- `session://{session_id}`: Get info about a session
- `sessions://`: List all active sessions

### Example: Testing with MCP Inspector

1. Start the MCP server:
   ```bash
   uv run mcp dev mcp_server.py
   ```
2. Open the [MCP Inspector](https://inspector.modelcontext.org/) and connect to your local server.

### Example: Registering with Claude Desktop

1. Start the server:
   ```bash
   uv run mcp install mcp_server.py --name "CodeBox-AI"
   ```
2. Open Claude Desktop and add your server as a custom tool.

## Prerequisites 

- Python 3.9+
- Docker
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer and resolver

## Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/codebox-ai.git
cd codebox-ai
```

2. Install dependencies with uv:

```bash
# Install uv if you don't have it yet
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create a virtual environment and install dependencies in one step
uv sync

# Or to install with development dependencies
uv sync --extra dev
```

3. Start the server:

```bash
uv run -m codeboxai.main
```

The API will be available at `http://localhost:8000`

### Development setup

For development, install with the development extras:
```bash
uv sync --extra "dev docs"
```

### Docker "file not found" error

If you encounter a "file not found" `DockerException` when running the server on MacOS, you might need to set the `DOCKER_HOST` environment variable. First, find out which context you are using by running:

```bash
docker context ls
```

Then set the `DOCKER_HOST` environment variable to the correct endpoint:

```bash
export DOCKER_HOST="unix:///Users/tconte/.docker/run/docker.sock"
```

## Usage

### Direct API Usage

1. Create a new session:

```bash
curl -X POST http://localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "dependencies": ["numpy", "pandas"]
  }'
```

2. Execute code in the session:

```bash
curl -X POST http://localhost:8000/execute \
  -H "Content-Type: application/json" \
  -d '{
    "code": "x = 42\nprint(f\"Value of x: {x}\")",
    "session_id": "YOUR_SESSION_ID"
  }'
```

3. Check execution status:

```bash
curl -X GET http://localhost:8000/execute/YOUR_REQUEST_ID/status
```

4. Get execution results:

```bash
curl -X GET http://localhost:8000/execute/YOUR_REQUEST_ID/results
```

5. Execute more code in the same session:

```bash
curl -X POST http://localhost:8000/execute \
  -H "Content-Type: application/json" \
  -d '{
    "code": "print(f\"x is still: {x}\")",
    "session_id": "YOUR_SESSION_ID"
  }'
```

### OpenAI GPT Integration Example

An example script is provided to demonstrate integration with OpenAI's GPT models.

1. Create a `.env` file in the project root:

```
AZURE_OPENAI_ENDPOINT=https://xxx.cognitiveservices.azure.com/
AZURE_OPENAI_API_KEY=foo
AZURE_OPENAI_DEPLOYMENT=gpt-4o
OPENAI_API_VERSION=2024-05-01-preview
```

2. Install additional requirements:

```bash
uv sync --extra "examples"
```

3. Run the example:

```bash
uv run examples/example_openai.py
```

This will start an interactive session where you can chat with GPT-4 and have it execute Python code. The script maintains state between executions, so variables and imports persist across interactions.

![Demo screencast](docs/images/readme_screencast.gif)

## API Endpoints

- `POST /sessions` - Create a new session
- `POST /execute` - Execute code in a session
- `GET /execute/{request_id}/status` - Get execution status
- `GET /execute/{request_id}/results` - Get execution results
- `DELETE /sessions/{session_id}` - Cleanup a session

## Security Notes

- Code execution is containerized using Docker
- Each session runs in an isolated environment
- Basic resource limits are implemented
- Network access is available but can be restricted
- Input code validation is implemented for basic security

## License

MIT License - See LICENSE file for details.

## A Note on Authorship

This code was pair-programmed with Claude 3.5 Sonnet (yes, an AI helping to build tools for other AIs - very meta). While I handled the product decisions and architecture reviews, Claude did most of the heavy lifting in terms of code generation and documentation. Even this README was written by Claude, which makes this acknowledgment a bit like an AI writing about an AI writing about AI tools... we need to go deeper 🤖✨

Humans were (mostly) present during the development process. No AIs were harmed in the making of this project, though a few might have gotten slightly dizzy from the recursion.

---
A prototype implementation, not intended for production use without additional security measures.
