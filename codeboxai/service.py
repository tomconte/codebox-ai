import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from codeboxai.kernel_manager import KernelManager

logger = logging.getLogger(__name__)


class CodeExecutionService:
    def __init__(self):
        self.kernel_manager = KernelManager()
        self.requests: Dict[str, Dict[str, Any]] = {}
        self.results: Dict[str, Dict[str, Any]] = {}
        self.sessions: Dict[str, Dict[str, Any]] = {}

    async def create_session(self, dependencies: Optional[List[str]] = None) -> str:
        """Create a new session with its own kernel"""
        session_id = str(uuid.uuid4())

        try:
            # Start a new kernel for this session
            self.kernel_manager.start_kernel(session_id)

            # Install dependencies if any
            if dependencies:
                deps_code = f"!pip install {' '.join(dependencies)}"
                deps_result = self.kernel_manager.execute_code(
                    session_id, deps_code)
                if deps_result['status'] == 'error':
                    raise ValueError(f"Failed to install dependencies: {
                                     deps_result['error']}")

            self.sessions[session_id] = {
                'created_at': datetime.utcnow().isoformat(),
                'last_used': datetime.utcnow().isoformat(),
                'dependencies': dependencies or []
            }

            logger.info(f"Created session {session_id}")

            return session_id

        except Exception as exc:
            # Cleanup if session creation fails
            logger.error(f"Error creating session: {exc}")
            if session_id in self.sessions:
                del self.sessions[session_id]
            self.kernel_manager.stop_kernel(session_id)
            raise

    async def create_execution_request(self, request_data: Dict[str, Any]) -> str:
        request_id = str(uuid.uuid4())
        session_id = request_data.get('session_id')

        # If no session_id provided, create a new session
        if not session_id:
            session_id = await self.create_session(request_data.get('dependencies'))

        # Verify session exists
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found")

        self.requests[request_id] = {
            'id': request_id,
            'session_id': session_id,
            'status': 'initializing',
            'code': request_data['code'],
            'created_at': datetime.utcnow().isoformat()
        }

        logger.info(f"Created execution request {request_id} in session {session_id}")

        return request_id

    async def execute_code(self, request_id: str):
        request_data = self.requests.get(request_id)
        if not request_data:
            return

        session_id = request_data['session_id']

        try:
            self.requests[request_id]['status'] = 'running'

            logger.info(f"Executing code for request {request_id}")

            result = self.kernel_manager.execute_code(
                session_id,  # Use session_id for kernel identification
                request_data['code']
            )

            # Update session last used timestamp
            self.sessions[session_id]['last_used'] = datetime.utcnow(
            ).isoformat()

            # Format outputs for API response
            formatted_outputs = []
            files = []

            for output in result['outputs']:
                if output['type'] == 'stream':
                    formatted_outputs.append({
                        'type': 'stream',
                        'content': output['text']
                    })
                elif output['type'] in ['execute_result', 'display_data']:
                    if 'image/png' in output['data']:
                        files.append(output['data']['image/png'])
                    if 'text/plain' in output['data']:
                        formatted_outputs.append({
                            'type': 'result',
                            'content': output['data']['text/plain']
                        })

            self.results[request_id] = {
                'status': result['status'],
                'output': formatted_outputs,
                'error': result['error'],
                'files': files,
                'completed_at': datetime.utcnow().isoformat()
            }

            logger.info(f"Code execution for request {request_id} completed with status: {result['status']}")

        except Exception as e:
            logger.error(f"Error executing code for request {request_id}: {e}")
            self.results[request_id] = {
                'status': 'error',
                'error': str(e),
                'completed_at': datetime.utcnow().isoformat()
            }

    def cleanup_session(self, session_id: str):
        """Cleanup a session and its kernel"""
        if session_id in self.sessions:
            self.kernel_manager.stop_kernel(session_id)
            del self.sessions[session_id]
