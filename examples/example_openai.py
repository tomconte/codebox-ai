import json
import time
import requests
from typing import List, Dict, Any
from openai import AzureOpenAI

import dotenv
dotenv.load_dotenv()

# Initialize OpenAI client
client = AzureOpenAI()  # Make sure OPENAI_API_KEY is set in your environment

# CodeBox-AI API configuration
CODEBOX_URL = "http://localhost:8000"


def execute_code(code: str, dependencies: List[str] = None) -> Dict[str, Any]:
    """Execute code using CodeBox-AI and return results"""
    url = f"{CODEBOX_URL}/execute"
    payload = {
        "code": code,
        "dependencies": dependencies or []
    }

    # Start execution
    response = requests.post(url, json=payload)
    response.raise_for_status()
    request_id = response.json()["request_id"]

    # Poll for results
    while True:
        status_response = requests.get(
            f"{CODEBOX_URL}/execute/{request_id}/status")
        status = status_response.json()

        if status["status"] in ["completed", "failed", "error"]:
            break

        time.sleep(1)

    # Get final results
    results = requests.get(f"{CODEBOX_URL}/execute/{request_id}/results")
    return results.json()


# Define available functions for OpenAI
functions = [
    {
        "name": "execute_python_code",
        "description": "Execute Python code in a secure environment with optional dependencies",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The Python code to execute"
                },
                "dependencies": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of Python packages to install before execution"
                }
            },
            "required": ["code", "dependencies"],
            "additionalProperties": False
        },
        "strict": True
    }
]


def chat_with_code_execution(user_message: str) -> None:
    """Chat with GPT-4 with code execution capabilities"""
    messages = [
        {"role": "system", "content": """You are a helpful AI assistant with the ability to execute Python code. 
        When a user asks you to perform calculations, create visualizations, or analyze data, you can write 
        and execute Python code to help them. Always explain your approach before executing code."""},
        {"role": "user", "content": user_message}
    ]

    while True:
        # Get completion from OpenAI
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=[{"type": "function", "function": f} for f in functions],
            tool_choice="auto"
        )

        message = response.choices[0].message
        messages.append({"role": "assistant", "content": message.content})

        # Check if the model wants to call a function
        if message.tool_calls:
            for tool_call in message.tool_calls:
                if tool_call.function.name == "execute_python_code":
                    # Parse the function arguments
                    try:
                        function_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        print("❌ Error: Invalid function arguments:", tool_call.function.arguments)
                        break

                    print("\n🤖 Assistant is executing code:")
                    print("```python")
                    print(function_args["code"])
                    print("```\n")

                    # Execute the code
                    result = execute_code(
                        function_args["code"],
                        function_args.get("dependencies", [])
                    )

                    # Print execution results
                    if result["stdout"]:
                        print("Output:")
                        print(result["stdout"])

                    if result["stderr"]:
                        print("Errors:")
                        print(result["stderr"])

                    if result.get("files"):
                        print("\nGenerated files:", result["files"])

                    # If any files were generated, download them using the API
                    for file in result.get("files", []):
                        response = requests.get(f"{CODEBOX_URL}/files/{file['path']}")
                        print(f"Downloaded file '{file['filename']}' length: {len(response.content)}")

                    # Rewrite the files in the result with full URLs
                    result["files"] = [f"{CODEBOX_URL}/files/{file['path']}" for file in result.get("files", [])]

                    # Add the tool_calls to the messages
                    messages.append({"role": "assistant", "tool_calls": [tool_call]})

                    # Add the function result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.function.name,
                        "content": json.dumps(result)
                    })

            # Get another completion with the function results
            continue

        # No more function calls, print the final response
        print("\n🤖 Assistant:", message.content)
        break


# Example usage
if __name__ == "__main__":
    examples = [
        "Create a simple bar plot showing the populations of 5 major cities, and save it to a PNG file",
        "Calculate the fibonacci sequence up to the 100th number and tell me some interesting properties about it",
        "Create a scatter plot of random data and add a trend line. Save it to a PNG file.",
        "Analyze this list of numbers and give me some statistics: 23, 45, 67, 89, 12, 34, 56, 78, 90, 21"
    ]

    print("🚀 CodeBox-AI OpenAI Integration Demo")
    print("\nExample queries:")
    for i, example in enumerate(examples, 1):
        print(f"{i}. {example}")
    print("\nEnter your query (or 'quit' to exit):")

    while True:
        user_input = input("\n> ")
        if user_input.lower() in ['quit', 'exit']:
            break

        try:
            chat_with_code_execution(user_input)
        except Exception as e:
            print(f"❌ Error: {e}")
            # Print stack trace for debugging
            import traceback
            traceback.print_exc()
