import base64
import json
import os
import time
from typing import Any, Dict, List, Optional

import dotenv
import requests
from kitty import kitty_display_image_file
from openai import AzureOpenAI

dotenv.load_dotenv()

# Initialize OpenAI client
client = AzureOpenAI()

# CodeBox-AI API configuration
CODEBOX_URL = "http://localhost:8000"

# You can change this to any local path you want to mount
# For example, /Users/yourusername/data, etc.
LOCAL_MOUNT_PATH = "/tmp"
CONTAINER_MOUNT_PATH = "/data"


class CodeBoxSession:
    """Manages a CodeBox-AI session"""

    def __init__(self, dependencies: Optional[List[str]] = None, execution_options: Optional[Dict[str, Any]] = None):
        self.session_id = self._create_session(dependencies, execution_options)

    def _create_session(
        self, dependencies: Optional[List[str]] = None, execution_options: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a new CodeBox session"""
        response = requests.post(
            f"{CODEBOX_URL}/sessions",
            json={"dependencies": dependencies or [], "execution_options": execution_options or {}},
        )
        response.raise_for_status()
        return response.json()["session_id"]

    def execute_code(self, code: str) -> Dict[str, Any]:
        """Execute code in the session"""
        # Submit code execution request
        execution_response = requests.post(f"{CODEBOX_URL}/execute", json={"code": code, "session_id": self.session_id})
        execution_response.raise_for_status()
        request_id = execution_response.json()["request_id"]

        # Poll for results
        while True:
            status_response = requests.get(f"{CODEBOX_URL}/execute/{request_id}/status")
            status = status_response.json()

            if status["status"] in ["completed", "failed", "error"]:
                break

            time.sleep(1)

        # Get final results
        results = requests.get(f"{CODEBOX_URL}/execute/{request_id}/results")
        return results.json()

    def cleanup(self):
        """Cleanup the session"""
        requests.delete(f"{CODEBOX_URL}/sessions/{self.session_id}")


# Define available functions for OpenAI
functions = [
    {
        "name": "execute_python_code",
        "description": "Execute Python code in a secure environment with state persistence",
        "parameters": {
            "type": "object",
            "properties": {"code": {"type": "string", "description": "The Python code to execute"}},
            "required": ["code"],
            "additionalProperties": False,
        },
        "strict": True,
    }
]


def chat_with_code_execution(user_message: str, messages: List[Dict], session: Optional[CodeBoxSession] = None) -> None:
    """Chat with GPT-4 with code execution capabilities"""
    # Create session if not provided
    own_session = False
    if session is None:
        session = CodeBoxSession(dependencies=["numpy", "pandas", "matplotlib"])
        own_session = True

    try:
        messages.append({"role": "user", "content": user_message})

        while True:
            # Get completion from OpenAI
            response = client.chat.completions.create(
                model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
                messages=messages,
                tools=[{"type": "function", "function": f} for f in functions],
                tool_choice="auto",
            )

            message = response.choices[0].message

            # If there's a content message, add it to the conversation
            if message.content:
                messages.append({"role": "assistant", "content": message.content})
                print("\n🤖 Assistant:", message.content)

            # Check if the model wants to call a function
            if message.tool_calls:
                # Add the assistant's message with tool calls
                messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": tool_call.id,
                                "type": "function",
                                "function": {
                                    "name": tool_call.function.name,
                                    "arguments": tool_call.function.arguments,
                                },
                            }
                            for tool_call in message.tool_calls
                        ],
                    }
                )

                # Process each tool call
                for tool_call in message.tool_calls:
                    if tool_call.function.name == "execute_python_code":
                        # Parse the function arguments
                        function_args = json.loads(tool_call.function.arguments)

                        print("\n🤖 Assistant is executing code:")
                        print("```python")
                        print(function_args["code"])
                        print("```\n")

                        # Execute the code
                        try:
                            result = session.execute_code(function_args["code"])
                        except Exception as exc:
                            # Also get the body of the message for error details
                            error_body = exc.response.json()
                            result = {"output": [], "error": f"{str(exc)}\n{error_body}", "files": []}

                        # Print execution results
                        if result.get("output"):
                            print("Output:")
                            for output in result["output"]:
                                if output["type"] == "stream":
                                    print(output["content"].strip())
                                elif output["type"] == "result":
                                    print(output["content"])

                        if result.get("error"):
                            print("Errors:")
                            print(result["error"])

                        if result.get("files"):
                            print(f"\nNumber of files: {len(result['files'])}")
                            # Save each file in the result to a temporary .png file
                            for i, file_data in enumerate(result["files"], 1):
                                file_path = f"output_{i}.png"
                                with open(file_path, "wb") as f:
                                    # file_data is a base64 str
                                    f.write(base64.b64decode(file_data))
                                print(f"File saved: {file_path}")
                                # Display the image using Kitty terminal
                                kitty_display_image_file(file_path)

                            # Remove files from the result to avoid sending back to the model
                            result["files"] = []

                        # Add the tool response to messages
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": tool_call.function.name,
                                "content": json.dumps(result),
                            }
                        )

                # Continue the conversation to handle the tool results
                continue

            # No more function calls, we're done
            break

    finally:
        # Cleanup session if we created it
        if own_session:
            session.cleanup()


# Example usage
if __name__ == "__main__":
    # Create a session for multiple interactions
    session = CodeBoxSession(
        dependencies=["numpy", "pandas", "matplotlib"],
        execution_options={
            "mount_points": [{"host_path": LOCAL_MOUNT_PATH, "container_path": CONTAINER_MOUNT_PATH, "read_only": True}]
        },
    )

    try:
        examples = [
            "Create a variable x = 42",
            "Print the value of x that we just created",
            "Create a scatter plot of 100 random points and add a trend line",
            "Calculate some statistics about the points we just plotted",
        ]

        messages = [
            {
                "role": "system",
                "content": """You are a helpful AI assistant with the ability to execute Python code. 
            When a user asks you to perform calculations, create visualizations, or analyze data, you can write 
            and execute Python code to help them. The code executes in a persistent session, so variables and 
            imports are maintained between executions. Always explain your approach before executing code.""",
            }
        ]

        print("🚀 CodeBox-AI OpenAI Integration Demo")
        print("\nExample queries (maintaining state between executions):")
        for i, example in enumerate(examples, 1):
            print(f"{i}. {example}")
        print("\nEnter your query (or 'quit' to exit):")

        while True:
            user_input = input("\n> ")
            if user_input.lower() in ["quit", "exit"]:
                break

            try:
                # Use the same session for all interactions
                chat_with_code_execution(user_input, messages=messages, session=session)
            except Exception as e:
                print(f"❌ Error: {e}")
                raise

    finally:
        # Cleanup the session
        session.cleanup()
