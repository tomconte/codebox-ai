import json
import logging
import uuid
import docker
import socket
import tempfile
import jupyter_client
from pathlib import Path
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)


class KernelManager:
    def __init__(self, image_name: str = "codeboxai-jupyter-base:latest"):
        self.docker_client = docker.from_env()
        self.image_name = image_name
        self.kernels: Dict[str, Dict[str, Any]] = {}
        self.connection_dir = Path(
            tempfile.mkdtemp(prefix='kernel_connections_'))
        self._ensure_kernel_image()

    def _ensure_kernel_image(self):
        try:
            self.docker_client.images.get(self.image_name)
        except docker.errors.ImageNotFound as exc:
            logger.info(f"Could not find image {self.image_name}: {exc}")
            logger.info(f"Building kernel image {self.image_name}...")
            dockerfile_dir = Path(__file__).parent
            self.docker_client.images.build(
                path=str(dockerfile_dir),
                dockerfile='Dockerfile.base_image',
                tag=self.image_name,
                quiet=False
            )

    def _find_free_port(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port

    def _create_connection_file(self, kernel_id: str) -> Tuple[dict, Path]:
        connection_file = self.connection_dir / f"kernel-{kernel_id}.json"
        ports = [self._find_free_port() for _ in range(5)]

        connection_info = {
            'shell_port': ports[0],
            'iopub_port': ports[1],
            'stdin_port': ports[2],
            'control_port': ports[3],
            'hb_port': ports[4],
            'ip': '0.0.0.0',
            'transport': 'tcp',
            'signature_scheme': 'hmac-sha256',
            'key': str(uuid.uuid4())
        }

        with open(connection_file, 'w') as f:
            json.dump(connection_info, f)

        return connection_info, connection_file

    def start_kernel(self, kernel_id: str) -> None:
        connection_info, connection_file = self._create_connection_file(
            kernel_id)

        port_bindings = {
            f"{connection_info['shell_port']}/tcp": connection_info['shell_port'],
            f"{connection_info['iopub_port']}/tcp": connection_info['iopub_port'],
            f"{connection_info['stdin_port']}/tcp": connection_info['stdin_port'],
            f"{connection_info['control_port']}/tcp": connection_info['control_port'],
            f"{connection_info['hb_port']}/tcp": connection_info['hb_port']
        }

        container_config = {
            'image': self.image_name,
            'command': [
                "python", "-m", "ipykernel_launcher",
                "-f", "/opt/connection/kernel.json"
            ],
            'volumes': {
                str(connection_file): {
                    'bind': '/opt/connection/kernel.json',
                    'mode': 'ro'
                }
            },
            'ports': port_bindings,
            'detach': True,
            'remove': True,
            'mem_limit': "2g",
            'cpu_count': 2,
            'environment': {
                'PYTHONPATH': '/opt/kernel'
            }
        }

        container = self.docker_client.containers.run(**container_config)

        client_connection = connection_info.copy()
        client_connection['ip'] = '127.0.0.1'

        client_file = self.connection_dir / f"client-{kernel_id}.json"
        with open(client_file, 'w') as f:
            json.dump(client_connection, f)

        client = jupyter_client.BlockingKernelClient()
        client.load_connection_file(str(client_file))

        self.kernels[kernel_id] = {
            'container': container,
            'client': client,
            'connection_file': connection_file,
            'client_file': client_file
        }

        client.start_channels()
        try:
            client.wait_for_ready(timeout=30)
        except RuntimeError as e:
            self.stop_kernel(kernel_id)
            raise RuntimeError(f"Kernel failed to start: {e}")

    def stop_kernel(self, kernel_id: str) -> None:
        if kernel_id in self.kernels:
            kernel_info = self.kernels[kernel_id]

            try:
                kernel_info['client'].stop_channels()
            except Exception as e:
                print(f"Error stopping client channels: {e}")

            try:
                kernel_info['container'].stop(timeout=5)
            except Exception as e:
                print(f"Error stopping container: {e}")

            for file_key in ['connection_file', 'client_file']:
                try:
                    kernel_info[file_key].unlink()
                except Exception as e:
                    print(f"Error removing {file_key}: {e}")

            del self.kernels[kernel_id]

    def execute_code(self, kernel_id: str, code: str, timeout: int = 60) -> Dict[str, Any]:
        if kernel_id not in self.kernels:
            raise ValueError(f"Kernel {kernel_id} not found")

        client = self.kernels[kernel_id]['client']
        _ = client.execute(code)

        result = {
            'status': 'error',
            'outputs': [],
            'error': None
        }

        while True:
            try:
                msg = client.get_iopub_msg(timeout=timeout)
                msg_type = msg['header']['msg_type']
                content = msg['content']

                if msg_type == 'status':
                    if content['execution_state'] == 'idle':
                        result['status'] = 'completed'
                        break

                elif msg_type == 'stream':
                    result['outputs'].append({
                        'type': 'stream',
                        'name': content['name'],
                        'text': content['text']
                    })

                elif msg_type in ['execute_result', 'display_data']:
                    output_data = {}

                    if 'image/png' in content.get('data', {}):
                        output_data['image/png'] = content['data']['image/png']

                    if 'image/svg+xml' in content.get('data', {}):
                        output_data['image/svg+xml'] = content['data']['image/svg+xml']

                    if 'text/html' in content.get('data', {}):
                        output_data['text/html'] = content['data']['text/html']

                    if 'text/plain' in content.get('data', {}):
                        output_data['text/plain'] = content['data']['text/plain']

                    result['outputs'].append({
                        'type': msg_type,
                        'data': output_data
                    })

                elif msg_type == 'error':
                    result['status'] = 'error'
                    result['error'] = {
                        'ename': content['ename'],
                        'evalue': content['evalue'],
                        'traceback': content['traceback']
                    }
                    break

            except Exception as e:
                result['status'] = 'error'
                result['error'] = f"Execution error: {str(e)}"
                break

        return result

    def cleanup(self):
        for kernel_id in list(self.kernels.keys()):
            self.stop_kernel(kernel_id)

        try:
            self.connection_dir.rmdir()
        except Exception as e:
            print(f"Error removing connection directory: {e}")
