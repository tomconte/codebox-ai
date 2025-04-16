import asyncio
import os
from codeboxai.models import MountPoint, ExecutionOptions, ExecutionRequest
from codeboxai.service import CodeExecutionService


async def main():
    # Initialize the service
    service = CodeExecutionService()

    # Create a mount point for Downloads directory
    downloads_dir = os.path.expanduser("~/Downloads")
    mount_points = [
        MountPoint(
            host_path=downloads_dir, container_path="/data/downloads", read_only=True  # Read-only access for security
        )
    ]

    # Configure execution options with mount points
    execution_options = ExecutionOptions(timeout=120, memory_limit="1G", mount_points=mount_points)

    # Create a session with the mount points
    session_id = await service.create_session(execution_options=execution_options)
    print(f"Created session with ID: {session_id}")

    # Example code that accesses files in the mounted directory
    code = """
# List files in the mounted directory
import os
print("Files in mounted directory:")
for file in os.listdir('/data/downloads'):
    print(f" - {file}")

# Read the first text file we find (if any)
text_files = [f for f in os.listdir('/data/downloads') if f.endswith('.txt')]
if text_files:
    with open(f'/data/downloads/{text_files[0]}', 'r') as f:
        print(f"\\nContents of {text_files[0]}:")
        print(f.read()[:500])  # Print first 500 chars
else:
    print("\\nNo text files found in the directory")
"""

    # Create an execution request
    request_id = await service.create_execution_request(ExecutionRequest(
        code=code,
        language="python",
        session_id=session_id,
    ))
    print(f"Created execution request with ID: {request_id}")

    # Execute the code
    await service.execute_code(request_id)

    # Get the results
    result = service.results.get(request_id)
    print("\nExecution Results:")
    for output in result.get("output", []):
        if output["type"] == "stream":
            print(output["content"])

    if result.get("error"):
        print(f"Error: {result['error']}")

    # Clean up the session when done
    service.cleanup_session(session_id)
    print("\nSession cleaned up")


if __name__ == "__main__":
    asyncio.run(main())
