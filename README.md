# CodeBox-AI

A secure Python code execution service that provides a self-hosted alternative to OpenAI's Code Interpreter. Built with FastAPI and IPython kernels, it supports session-based code execution and integrates with LLM function calling.

## Features

- Session-based Python code execution in Docker containers
- IPython kernel for rich output support
- Dynamic package installation
- State persistence between executions
- Support for plotting and visualization

## Prerequisites 

- Python 3.9+
- Docker

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/codebox-ai.git
cd codebox-ai
```

2. Install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
pip install -r requirements.txt
```

3. Start the server:
```bash
uvicorn codeboxai.main:app --reload
```

The API will be available at `http://localhost:8000`

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

3. Execute more code in the same session:
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
pip install -r examples/requirements.txt
```

3. Run the example:
```bash
python examples/example_openai.py
```

This will start an interactive session where you can chat with GPT-4 and have it execute Python code. The script maintains state between executions, so variables and imports persist across interactions.

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
