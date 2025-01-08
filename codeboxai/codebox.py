import logging
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import docker
from pydantic import BaseModel, Field, field_validator

# Set up logging
logger = logging.getLogger(__name__)

# Safe packages that are allowed to be installed
ALLOWED_PACKAGES = {
    'indsl',
    'numpy',
    'pandas',
    'matplotlib',
    'seaborn',
    'scikit-learn',
    'requests',
    'beautifulsoup4',
    'pillow',
    'nltk',
    'opencv-python',
    'prophet',
    'scipy',
    'stumpy',
    'tensorflow',
    'torch',
    'transformers',
}


class Storage:
    """Simple (prototype) in-memory storage for requests and results."""
    def __init__(self):
        self.requests = {}
        self.results = {}


class ExecutionOptions(BaseModel):
    """Options for execution."""
    timeout: int = Field(default=300, ge=1, le=600)
    memory_limit: str = Field(default="2G")
    cpu_limit: str = Field(default="1")
    environment_variables: Optional[Dict[str, str]] = None


class ExecutionRequest(BaseModel):
    """Request to execute a code snippet."""
    code: str = Field(max_length=10000)
    language: str = Field(default="python", pattern="^python$")
    dependencies: Optional[List[str]] = Field(default_factory=list)
    execution_options: ExecutionOptions = Field(
        default_factory=ExecutionOptions)

    @field_validator('code')
    @classmethod
    def validate_code(cls, code: str) -> str:
        forbidden_keywords = [
            'import os',
            'import sys',
            'subprocess',
            '__import__'
        ]
        for keyword in forbidden_keywords:
            if keyword in code:
                logger.error(f"Potentially dangerous code: {keyword} not allowed")
                raise ValueError(f"Potentially dangerous code: {keyword} not allowed")
        return code

    @field_validator('dependencies')
    @classmethod
    def validate_dependencies(cls, dependencies: List[str]) -> List[str]:
        if not dependencies:
            return dependencies

        # Remove any version specifiers for validation
        base_packages = {pkg.split('==')[0].split('>=')[0].split('<=')[
            0] for pkg in dependencies}

        # Check against allowed packages
        invalid_packages = base_packages - ALLOWED_PACKAGES
        if invalid_packages:
            logger.error(
                f"Following packages are not allowed: {', '.join(invalid_packages)}."
            )
            raise ValueError(
                f"Following packages are not allowed: {
                    ', '.join(invalid_packages)}. "
                f"Allowed packages are: {', '.join(sorted(ALLOWED_PACKAGES))}"
            )
        return dependencies


class FileStore:
    """Simple (prototype) file storage helper."""
    def __init__(self, base_path: str = "storage"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def store_file(self, request_id: str, file_path: Path) -> str:
        """Store a file for a specific request"""
        logger.info(f"Storing file {file_path.name} for request {request_id}")

        request_dir = self.base_path / request_id
        request_dir.mkdir(parents=True, exist_ok=True)

        # Copy file to storage
        dest_path = request_dir / file_path.name
        shutil.copy2(file_path, dest_path)

        return str(dest_path.relative_to(self.base_path))

    def get_file_path(self, request_id: str, filename: str) -> Path:
        """Get path for a stored file"""
        return self.base_path / request_id / filename

    def list_files(self, request_id: str) -> list:
        """List all files for a request"""
        request_dir = self.base_path / request_id
        if not request_dir.exists():
            return []
        return [f.name for f in request_dir.iterdir() if f.is_file()]

    def cleanup_old_files(self, max_age_hours: int = 24):
        """Clean up files older than specified hours"""
        current_time = datetime.now()
        for request_dir in self.base_path.iterdir():
            if not request_dir.is_dir():
                continue

            dir_time = datetime.fromtimestamp(request_dir.stat().st_mtime)
            if current_time - dir_time > timedelta(hours=max_age_hours):
                shutil.rmtree(request_dir)


class CodeBoxService:
    """Service to execute code snippets in a secure environment."""
    def __init__(self, storage: Storage):
        self.docker_client = docker.from_env()
        self.base_temp_dir = tempfile.mkdtemp(prefix='codebox_')
        self.file_store = FileStore()
        self.storage = storage

    def _create_dockerfile(self, work_dir: str, dependencies: List[str]) -> str:
        """Create a Dockerfile with the specified dependencies"""
        dockerfile_content = [
            "FROM python:3.9-slim",
            "WORKDIR /mnt/data",

            # Install system dependencies if needed
            "RUN apt-get update && apt-get install -y --no-install-recommends \\\n",
            "    gcc \\\n",
            "    python3-dev \\\n",
            "    && rm -rf /var/lib/apt/lists/*",

            # Install Python dependencies
            "COPY requirements.txt .",
            "RUN pip install --no-cache-dir -r requirements.txt",

            # Copy the script
            "COPY main.py .",
            "CMD [\"python\", \"main.py\"]"
        ]

        # Write Dockerfile
        dockerfile_path = os.path.join(work_dir, "Dockerfile")
        with open(dockerfile_path, "w") as f:
            f.write("\n".join(dockerfile_content))

        # Write requirements.txt
        requirements_path = os.path.join(work_dir, "requirements.txt")
        with open(requirements_path, "w") as f:
            f.write("\n".join(dependencies))

        return dockerfile_path

    async def create_execution_request(self, request: ExecutionRequest) -> str:
        request_id = str(uuid.uuid4())

        request_data = {
            'id': request_id,
            'status': 'queued',
            'code': request.code,
            'dependencies': request.dependencies,
            'options': request.execution_options.dict(),
            'created_at': datetime.utcnow().isoformat()
        }

        self.storage.requests[request_id] = request_data
        return request_id

    async def execute_in_docker(self, request_id: str):
        request_data = self.storage.requests.get(request_id)
        if not request_data:
            return

        work_dir = os.path.join(self.base_temp_dir, request_id)
        os.makedirs(work_dir, exist_ok=True)
        container = None

        try:
            # Create Python script
            script_path = os.path.join(work_dir, 'main.py')
            with open(script_path, 'w') as f:
                f.write(request_data['code'])

            # Update status
            self.storage.requests[request_id]['status'] = 'building'

            # Create Dockerfile and build image
            dockerfile_path = self._create_dockerfile(
                work_dir, request_data['dependencies'])

            # Build custom image
            logger.info(f"Building Docker image for request {request_id}")
            image, build_logs = self.docker_client.images.build(
                path=work_dir,
                dockerfile=dockerfile_path,
                rm=True
            )

            # Update status
            self.storage.requests[request_id]['status'] = 'running'

            # Run container with custom image
            logger.info(f"Running Docker container for request {request_id}")
            container = self.docker_client.containers.run(
                image.id,
                volumes={
                    work_dir: {'bind': '/mnt/data', 'mode': 'rw'}
                },
                working_dir='/mnt/data',
                mem_limit=request_data['options']['memory_limit'],
                cpu_period=100000,
                cpu_quota=int(
                    float(request_data['options']['cpu_limit']) * 100000),
                remove=False,
                detach=True
            )

            # Wait for completion
            result = container.wait()
            exit_code = result['StatusCode']

            # Collect outputs
            stdout = container.logs(stdout=True, stderr=False).decode('utf-8')
            stderr = container.logs(stdout=False, stderr=True).decode('utf-8')

            # Store results
            self.storage.results[request_id] = {
                'status': 'completed' if exit_code == 0 else 'failed',
                'exit_code': exit_code,
                'stdout': stdout,
                'stderr': stderr,
                'completed_at': datetime.utcnow().isoformat(),
                'dependencies_installed': request_data['dependencies']
            }

            # After successful execution, store generated files
            generated_files = []
            work_dir_path = Path(work_dir)
            for file_path in work_dir_path.iterdir():
                if file_path.name not in ['main.py', 'Dockerfile', 'requirements.txt']:
                    stored_path = self.file_store.store_file(
                        request_id, file_path)
                    generated_files.append({
                        'filename': file_path.name,
                        'path': stored_path
                    })

            self.storage.results[request_id]['files'] = generated_files

        except Exception as e:
            logger.exception(f"Error executing request {request_id}: {e}")
            self.storage.results[request_id] = {
                'status': 'error',
                'error_message': str(e),
                'completed_at': datetime.utcnow().isoformat()
            }

        finally:
            # Clean up container and image
            if container:
                try:
                    container.remove(force=True)
                except Exception as e:
                    print(f"Error removing container: {e}")

            # Clean up working directory
            try:
                shutil.rmtree(work_dir, ignore_errors=True)
            except Exception as e:
                print(f"Error removing working directory: {e}")
