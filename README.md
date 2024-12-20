# CodeBox-AI 🤖

CodeBox-AI is a PROTOTYPE secure Python code execution service designed to replicate OpenAI's Code Interpreter capabilities. It provides a secure environment for executing arbitrary Python code with dependency management and file handling capabilities.

## Integration with LLMs 🧠

CodeBox-AI is designed to be used in conjunction with Large Language Models (LLMs) through their function calling capabilities. It can be seamlessly integrated with:
- OpenAI GPT function calling
- Anthropic Claude function calling
- Other LLMs supporting structured function calls

This enables you to create powerful AI assistants that can execute Python code, analyze data, create visualizations, and handle file operations in a secure environment.

## Features ✨

- 🔒 Secure code execution in isolated Docker containers
- 📦 Dynamic Python package installation
- 🗃️ File output handling and storage
- 🔄 Asynchronous execution with status tracking
- 📊 Support for data science libraries
- 🛡️ Resource usage limits and security constraints

## Quick Start 🚀

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

## LLM integration example 🤝

### OpenAI

- [examples/example_openai.py](examples/example_openai.py)

## API Usage 📚

### Execute Code
```bash
curl -X POST http://localhost:8000/execute \
  -H "Content-Type: application/json" \
  -d '{
    "code": "print(\"Hello from CodeBox-AI!\")",
    "dependencies": ["numpy", "pandas"],
    "execution_options": {
      "timeout": 300,
      "memory_limit": "2G"
    }
  }'
```

### Check Execution Status
```bash
curl http://localhost:8000/execute/{request_id}/status
```

### Get Results
```bash
curl http://localhost:8000/execute/{request_id}/results
```

### Download Generated Files
```bash
curl http://localhost:8000/files/{request_id}/{filename}
```

## Data Science Example 📊

Here's an example that generates a plot using matplotlib:

```bash
curl -X POST http://localhost:8000/execute \
  -H "Content-Type: application/json" \
  -d '{
    "code": "
      import numpy as np
      import matplotlib.pyplot as plt
      
      x = np.linspace(0, 10, 100)
      y = np.sin(x)
      plt.plot(x, y)
      plt.savefig(\"sine_wave.png\")
      print(\"Plot saved!\")
    ",
    "dependencies": ["numpy", "matplotlib"]
  }'
```

## Security Features 🛡️

- Containerized execution environment
- Whitelisted Python packages
- Resource usage limits (CPU, memory)
- Automatic file cleanup
- Input code validation

## Supported Packages 📦

The following packages are currently allowed to be installed:
- numpy
- pandas
- matplotlib
- seaborn
- scikit-learn
- requests
- beautifulsoup4
- pillow
- nltk
- opencv-python
- tensorflow
- torch
- transformers

## Architecture 🏗️

The system consists of several key components:
1. FastAPI web service
2. Docker container manager
3. Package dependency handler
4. File storage system
5. Execution queue manager

## License 📄

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer ⚠️

This is a prototype implementation and should not be used in production without additional security measures and thorough testing.
