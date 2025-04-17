"""Tests for the KernelManager class."""

import uuid
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import docker
import pytest

from codeboxai.kernel_manager import KernelManager
from codeboxai.models import MountPoint


@pytest.fixture
def mock_docker_client():
    """Mock Docker client fixture."""
    mock_client = MagicMock()
    # Mock API version
    mock_client.api.version.return_value = "1.41"

    # Setup images mock
    mock_image = MagicMock()
    mock_image.tags = ["codeboxai-jupyter-base:latest"]
    mock_client.images.list.return_value = [mock_image]
    mock_client.images.get.return_value = mock_image

    # Setup container mock
    mock_container = MagicMock()
    mock_container.status = "running"
    mock_container.logs.return_value = b"Container started successfully"
    mock_client.containers.run.return_value = mock_container

    return mock_client


@pytest.fixture
def mock_jupyter_client():
    """Mock Jupyter client fixture."""
    mock_client = MagicMock()
    mock_client.start_channels.return_value = None
    mock_client.wait_for_ready.return_value = True

    # Setup message responses for code execution
    def mock_get_iopub_msg(timeout=None):
        # First return a status message with 'busy' state
        # Then return a stream output
        # Finally return a status message with 'idle' state
        if not hasattr(mock_get_iopub_msg, "call_count"):
            mock_get_iopub_msg.call_count = 0

        mock_get_iopub_msg.call_count += 1

        if mock_get_iopub_msg.call_count == 1:
            return {"header": {"msg_type": "status"}, "content": {"execution_state": "busy"}}
        elif mock_get_iopub_msg.call_count == 2:
            return {"header": {"msg_type": "stream"}, "content": {"name": "stdout", "text": "Hello, world!"}}
        else:
            return {"header": {"msg_type": "status"}, "content": {"execution_state": "idle"}}

    mock_client.get_iopub_msg.side_effect = mock_get_iopub_msg
    return mock_client


@pytest.fixture
def kernel_manager():
    """Create a KernelManager instance with mocked dependencies."""
    with patch("docker.from_env") as mock_docker_from_env:
        mock_client = MagicMock()
        mock_client.api.version.return_value = "1.41"
        mock_image = MagicMock()
        mock_image.tags = ["codeboxai-jupyter-base:latest"]
        mock_client.images.list.return_value = [mock_image]
        mock_client.images.get.return_value = mock_image
        mock_container = MagicMock()
        mock_container.status = "running"
        mock_container.logs.return_value = b"Container started successfully"
        mock_client.containers.run.return_value = mock_container
        mock_docker_from_env.return_value = mock_client

        with patch("tempfile.mkdtemp") as mock_mkdtemp:
            mock_mkdtemp.return_value = "/tmp/kernel_connections"
            manager = KernelManager()
            yield manager


def test_init():
    """Test KernelManager initialization."""
    with patch("docker.from_env") as mock_docker_from_env:
        mock_client = MagicMock()
        mock_docker_from_env.return_value = mock_client

        with patch("tempfile.mkdtemp", return_value="/tmp/kernel_connections"):
            manager = KernelManager()

            assert manager.docker_client == mock_client
            assert manager.image_name == "codeboxai-jupyter-base:latest"
            assert isinstance(manager.kernels, dict)
            assert manager.connection_dir == Path("/tmp/kernel_connections")

            # Verify _ensure_kernel_image was called during init
            mock_client.images.get.assert_called_once_with(manager.image_name)


def test_init_docker_error():
    """Test handling of Docker client initialization errors."""
    with patch("docker.from_env", side_effect=Exception("Docker error")):
        with pytest.raises(Exception) as exc_info:
            KernelManager()
        assert "Docker error" in str(exc_info.value)


def test_ensure_kernel_image_exists(kernel_manager):
    """Test _ensure_kernel_image when image already exists."""
    # Reset mock to clear the call from initialization
    kernel_manager.docker_client.images.get.reset_mock()

    # Call the method directly
    kernel_manager._ensure_kernel_image()

    # Verify the method checked for the image
    kernel_manager.docker_client.images.get.assert_called_once_with(kernel_manager.image_name)

    # Verify it didn't try to build the image
    kernel_manager.docker_client.images.build.assert_not_called()


def test_ensure_kernel_image_build(kernel_manager):
    """Test _ensure_kernel_image when image needs to be built."""
    # Make the get() method raise ImageNotFound
    kernel_manager.docker_client.images.get.side_effect = docker.errors.ImageNotFound("Image not found")

    # Call the method
    kernel_manager._ensure_kernel_image()

    # Verify build was called with correct parameters
    kernel_manager.docker_client.images.build.assert_called_once()
    args, kwargs = kernel_manager.docker_client.images.build.call_args
    assert kwargs["tag"] == kernel_manager.image_name
    assert kwargs["dockerfile"] == "Dockerfile.base_image"
    assert "path" in kwargs


def test_find_free_port():
    """Test _find_free_port method."""
    # Create a separate version of the test that doesn't rely on fixture
    with patch("docker.from_env"):
        # Create a mock socket that only responds to the getsockname() method
        with patch("socket.socket") as mock_socket_constructor:
            mock_socket = MagicMock()
            mock_socket.getsockname.return_value = ("127.0.0.1", 12345)
            mock_socket_constructor.return_value.__enter__.return_value = mock_socket

            # Create KernelManager with minimal dependencies
            with patch("tempfile.mkdtemp", return_value="/tmp/kernel_connections"):
                manager = KernelManager()

                # Test the _find_free_port directly
                port = manager._find_free_port()

                # Assertions
                assert port == 12345
                mock_socket.bind.assert_called_once_with(("", 0))
                mock_socket.listen.assert_called_once_with(1)
                mock_socket.getsockname.assert_called_once()


def test_create_connection_file():
    """Test _create_connection_file method."""
    kernel_id = "test-kernel"
    with patch("docker.from_env") as mock_docker:
        mock_docker.return_value = MagicMock()
        with patch("tempfile.mkdtemp", return_value="/tmp/kernel_connections"):
            with patch("socket.socket"):
                manager = KernelManager()
                manager.connection_dir = Path("/tmp/kernel_connections")
                with patch.object(manager, "_find_free_port", side_effect=[1000, 1001, 1002, 1003, 1004]):
                    m = mock_open()
                    with patch("builtins.open", m):
                        with patch("uuid.uuid4", return_value=uuid.UUID("12345678-1234-5678-1234-567812345678")):
                            with patch("json.dump") as mock_json_dump:
                                connection_info, connection_file = manager._create_connection_file(kernel_id)
    assert connection_info["shell_port"] == 1000
    assert connection_info["iopub_port"] == 1001
    assert connection_info["stdin_port"] == 1002
    assert connection_info["control_port"] == 1003
    assert connection_info["hb_port"] == 1004
    assert connection_info["ip"] == "0.0.0.0"
    assert connection_info["transport"] == "tcp"
    assert connection_info["signature_scheme"] == "hmac-sha256"
    assert connection_info["key"] == "12345678-1234-5678-1234-567812345678"
    expected_path = Path("/tmp/kernel_connections") / f"kernel-{kernel_id}.json"
    assert connection_file == expected_path
    m.assert_called_once_with(expected_path, "w")
    # Check that json.dump was called with the correct data
    mock_json_dump.assert_called_once_with(connection_info, m())


def test_start_kernel(kernel_manager):
    """Test start_kernel method."""
    kernel_id = "test-kernel"

    # Mock necessary methods and dependencies
    with patch.object(kernel_manager, "_create_connection_file") as mock_create_file:
        mock_create_file.return_value = (
            {
                "shell_port": 1000,
                "iopub_port": 1001,
                "stdin_port": 1002,
                "control_port": 1003,
                "hb_port": 1004,
                "ip": "0.0.0.0",
                "transport": "tcp",
                "signature_scheme": "hmac-sha256",
                "key": "test-key",
            },
            Path("/tmp/kernel_connections/kernel-test-kernel.json"),
        )

        # Mock open function
        m = mock_open()
        with patch("builtins.open", m):
            # Mock BlockingKernelClient
            mock_client = MagicMock()
            with patch("jupyter_client.BlockingKernelClient", return_value=mock_client):
                kernel_manager.start_kernel(kernel_id)

    # Verify Docker container was started with correct parameters
    kernel_manager.docker_client.containers.run.assert_called_once()
    args, kwargs = kernel_manager.docker_client.containers.run.call_args

    # Check important container configurations
    assert kwargs["image"] == kernel_manager.image_name
    assert kwargs["command"] == ["python", "-m", "ipykernel_launcher", "-f", "/opt/connection/kernel.json"]
    assert "/tmp/kernel_connections/kernel-test-kernel.json" in kwargs["volumes"]

    # Verify client was properly set up
    assert kernel_id in kernel_manager.kernels
    assert mock_client.start_channels.called
    assert mock_client.wait_for_ready.called


def test_start_kernel_with_mount_points():
    """Test start_kernel method with custom mount points."""
    with patch("docker.from_env") as mock_docker_from_env:
        mock_client = MagicMock()
        mock_container = MagicMock()
        mock_container.status = "running"
        mock_client.containers.run.return_value = mock_container
        mock_docker_from_env.return_value = mock_client
        with patch("tempfile.mkdtemp", return_value="/tmp/kernel_connections"):
            with patch("socket.socket"):
                with patch("pathlib.Path.exists", return_value=True):
                    manager = KernelManager(image_name="test-image")
                    manager.connection_dir = Path("/tmp/kernel_connections")
                    kernel_id = "test-kernel"
                    mount_points = [
                        MountPoint(host_path="/host/path1", container_path="/container/path1", read_only=True),
                        MountPoint(host_path="/host/path2", container_path="/container/path2", read_only=False),
                    ]
                    connection_info = {
                        "shell_port": 1000,
                        "iopub_port": 1001,
                        "stdin_port": 1002,
                        "control_port": 1003,
                        "hb_port": 1004,
                        "ip": "0.0.0.0",
                        "transport": "tcp",
                        "signature_scheme": "hmac-sha256",
                        "key": "test-key",
                    }
                    connection_file = Path("/tmp/kernel_connections/kernel-test-kernel.json")
                    with patch.object(
                        manager, "_create_connection_file", return_value=(connection_info, connection_file)
                    ):
                        with patch("builtins.open", mock_open()):
                            with patch("json.dump") as mock_json_dump:
                                mock_jupyter_client = MagicMock()
                                with patch("jupyter_client.BlockingKernelClient", return_value=mock_jupyter_client):
                                    manager.start_kernel(kernel_id, mount_points)
    mock_client.containers.run.assert_called_once()
    args, kwargs = mock_client.containers.run.call_args
    assert kwargs["image"] == "test-image"
    assert kwargs["command"] == ["python", "-m", "ipykernel_launcher", "-f", "/opt/connection/kernel.json"]
    volumes = kwargs["volumes"]
    assert len(volumes) == 3
    assert str(connection_file) in volumes
    assert "/host/path1" in volumes
    assert "/host/path2" in volumes
    assert volumes["/host/path1"]["mode"] == "ro"
    assert volumes["/host/path2"]["mode"] == "rw"
    assert volumes["/host/path1"]["bind"] == "/container/path1"
    assert volumes["/host/path2"]["bind"] == "/container/path2"
    # json.dump should be called for both connection and client files
    assert mock_json_dump.call_count >= 1


def test_start_kernel_container_fail(kernel_manager):
    """Test start_kernel when container fails to start."""
    kernel_id = "test-kernel"

    # Configure mock container to report failed status
    mock_container = MagicMock()
    mock_container.status = "exited"
    mock_container.logs.return_value = b"Container failed to start"
    kernel_manager.docker_client.containers.run.return_value = mock_container

    # Mock necessary methods and dependencies
    with patch.object(kernel_manager, "_create_connection_file") as mock_create_file:
        mock_create_file.return_value = (
            {
                "shell_port": 1000,
                "iopub_port": 1001,
                "stdin_port": 1002,
                "control_port": 1003,
                "hb_port": 1004,
                "ip": "0.0.0.0",
                "transport": "tcp",
                "signature_scheme": "hmac-sha256",
                "key": "test-key",
            },
            Path("/tmp/kernel_connections/kernel-test-kernel.json"),
        )

        # Mock open function
        m = mock_open()
        with patch("builtins.open", m):
            # Mock BlockingKernelClient
            mock_client = MagicMock()
            with patch("jupyter_client.BlockingKernelClient", return_value=mock_client):
                with pytest.raises(RuntimeError) as exc_info:
                    kernel_manager.start_kernel(kernel_id)

                assert "Kernel container failed to start" in str(exc_info.value)

                # Verify container was removed
                mock_container.remove.assert_called_once()


def test_stop_kernel(kernel_manager):
    """Test stop_kernel method."""
    kernel_id = "test-kernel"

    # Set up a mock kernel
    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_connection_file = MagicMock()
    mock_client_file = MagicMock()

    kernel_manager.kernels[kernel_id] = {
        "client": mock_client,
        "container": mock_container,
        "connection_file": mock_connection_file,
        "client_file": mock_client_file,
    }

    # Call stop_kernel
    kernel_manager.stop_kernel(kernel_id)

    # Verify all cleanup operations were called
    mock_client.stop_channels.assert_called_once()
    mock_container.stop.assert_called_once_with(timeout=5)
    mock_container.remove.assert_called_once()
    mock_connection_file.unlink.assert_called_once()
    mock_client_file.unlink.assert_called_once()

    # Verify kernel was removed from kernels dictionary
    assert kernel_id not in kernel_manager.kernels


def test_stop_kernel_error_handling(kernel_manager):
    """Test stop_kernel error handling."""
    kernel_id = "test-kernel"

    # Set up a mock kernel with components that raise exceptions
    mock_client = MagicMock()
    mock_client.stop_channels.side_effect = Exception("Client error")

    mock_container = MagicMock()
    mock_container.stop.side_effect = Exception("Container stop error")
    mock_container.remove.side_effect = Exception("Container remove error")

    mock_connection_file = MagicMock()
    mock_connection_file.unlink.side_effect = Exception("Connection file error")

    mock_client_file = MagicMock()
    mock_client_file.unlink.side_effect = Exception("Client file error")

    kernel_manager.kernels[kernel_id] = {
        "client": mock_client,
        "container": mock_container,
        "connection_file": mock_connection_file,
        "client_file": mock_client_file,
    }

    # The method should not raise exceptions even if components fail
    kernel_manager.stop_kernel(kernel_id)

    # Verify all cleanup operations were called
    mock_client.stop_channels.assert_called_once()
    mock_container.stop.assert_called_once_with(timeout=5)
    mock_container.remove.assert_called_once()
    mock_connection_file.unlink.assert_called_once()
    mock_client_file.unlink.assert_called_once()

    # Verify kernel was removed from kernels dictionary despite errors
    assert kernel_id not in kernel_manager.kernels


def test_execute_code(kernel_manager, mock_jupyter_client):
    """Test execute_code method."""
    kernel_id = "test-kernel"

    # Set up a mock kernel
    kernel_manager.kernels[kernel_id] = {
        "client": mock_jupyter_client,
        "container": MagicMock(),
        "connection_file": MagicMock(),
        "client_file": MagicMock(),
    }

    # Execute code
    result = kernel_manager.execute_code(kernel_id, "print('Hello, world!')")

    # Verify execute was called on the client
    mock_jupyter_client.execute.assert_called_once_with("print('Hello, world!')")

    # Verify result has the expected structure and content
    assert result["status"] == "completed"
    assert len(result["outputs"]) == 1
    assert result["outputs"][0]["type"] == "stream"
    assert result["outputs"][0]["text"] == "Hello, world!"
    assert result["error"] is None


def test_execute_code_kernel_not_found(kernel_manager):
    """Test execute_code with a non-existent kernel."""
    with pytest.raises(ValueError) as exc_info:
        kernel_manager.execute_code("nonexistent-kernel", "print('Hello')")
    assert "Kernel nonexistent-kernel not found" in str(exc_info.value)


def test_execute_code_error(kernel_manager, mock_jupyter_client):
    """Test execute_code when an error occurs."""
    kernel_id = "test-kernel"

    # Set up a mock kernel
    kernel_manager.kernels[kernel_id] = {
        "client": mock_jupyter_client,
        "container": MagicMock(),
        "connection_file": MagicMock(),
        "client_file": MagicMock(),
    }

    # Configure mock to return error message
    def mock_get_iopub_msg(timeout=None):
        return {
            "header": {"msg_type": "error"},
            "content": {
                "ename": "NameError",
                "evalue": "name 'x' is not defined",
                "traceback": ["Traceback...", "NameError: name 'x' is not defined"],
            },
        }

    mock_jupyter_client.get_iopub_msg.side_effect = mock_get_iopub_msg

    # Execute code
    result = kernel_manager.execute_code(kernel_id, "print(x)")

    # Verify result contains error information
    assert result["status"] == "error"
    assert result["error"] is not None
    assert result["error"]["ename"] == "NameError"
    assert result["error"]["evalue"] == "name 'x' is not defined"
    assert len(result["error"]["traceback"]) == 2


def test_execute_code_timeout(kernel_manager, mock_jupyter_client):
    """Test execute_code with timeout."""
    kernel_id = "test-kernel"

    # Set up a mock kernel
    kernel_manager.kernels[kernel_id] = {
        "client": mock_jupyter_client,
        "container": MagicMock(),
        "connection_file": MagicMock(),
        "client_file": MagicMock(),
    }

    # Configure mock to raise timeout exception
    mock_jupyter_client.get_iopub_msg.side_effect = TimeoutError("Execution timed out")

    # Execute code
    result = kernel_manager.execute_code(kernel_id, "while True: pass", timeout=1)

    # Verify result contains error information
    assert result["status"] == "error"
    assert "Execution error: Execution timed out" in result["error"]


def test_cleanup(kernel_manager):
    """Test cleanup method."""
    # Add some mock kernels
    kernel_manager.kernels = {
        "kernel1": {
            "client": MagicMock(),
            "container": MagicMock(),
            "connection_file": MagicMock(),
            "client_file": MagicMock(),
        },
        "kernel2": {
            "client": MagicMock(),
            "container": MagicMock(),
            "connection_file": MagicMock(),
            "client_file": MagicMock(),
        },
    }

    # Mock stop_kernel to track calls
    with patch.object(kernel_manager, "stop_kernel") as mock_stop:
        # Mock rmdir
        mock_connection_dir = MagicMock()
        kernel_manager.connection_dir = mock_connection_dir

        # Call cleanup
        kernel_manager.cleanup()

        # Verify all kernels were stopped
        assert mock_stop.call_count == 2
        mock_stop.assert_any_call("kernel1")
        mock_stop.assert_any_call("kernel2")

        # Verify connection directory was removed
        mock_connection_dir.rmdir.assert_called_once()


def test_cleanup_rmdir_error(kernel_manager):
    """Test cleanup when rmdir raises an exception."""
    # Mock stop_kernel to avoid side effects
    with patch.object(kernel_manager, "stop_kernel"):
        # Mock rmdir to raise exception
        mock_connection_dir = MagicMock()
        mock_connection_dir.rmdir.side_effect = Exception("Directory not empty")
        kernel_manager.connection_dir = mock_connection_dir

        # Call cleanup - should not raise exception
        kernel_manager.cleanup()

        # Verify rmdir was called
        mock_connection_dir.rmdir.assert_called_once()


def test_execute_code_with_different_output_types(kernel_manager):
    """Test execute_code with different output types."""
    kernel_id = "test-kernel"

    # Set up a mock kernel
    mock_client = MagicMock()
    kernel_manager.kernels[kernel_id] = {
        "client": mock_client,
        "container": MagicMock(),
        "connection_file": MagicMock(),
        "client_file": MagicMock(),
    }

    # Configure mock to return different output types
    def mock_get_iopub_msg(timeout=None):
        if not hasattr(mock_get_iopub_msg, "call_count"):
            mock_get_iopub_msg.call_count = 0

        mock_get_iopub_msg.call_count += 1

        if mock_get_iopub_msg.call_count == 1:
            return {
                "header": {"msg_type": "execute_result"},
                "content": {"data": {"text/plain": "42", "text/html": "<b>42</b>", "image/png": "base64_image_data"}},
            }
        elif mock_get_iopub_msg.call_count == 2:
            return {"header": {"msg_type": "display_data"}, "content": {"data": {"image/svg+xml": "<svg>...</svg>"}}}
        else:
            return {"header": {"msg_type": "status"}, "content": {"execution_state": "idle"}}

    mock_client.get_iopub_msg.side_effect = mock_get_iopub_msg

    # Execute code
    result = kernel_manager.execute_code(kernel_id, "display(42)")

    # Verify result contains different output types
    assert result["status"] == "completed"
    assert len(result["outputs"]) == 2

    # Check execute_result output
    assert result["outputs"][0]["type"] == "execute_result"
    assert "text/plain" in result["outputs"][0]["data"]
    assert "text/html" in result["outputs"][0]["data"]
    assert "image/png" in result["outputs"][0]["data"]

    # Check display_data output
    assert result["outputs"][1]["type"] == "display_data"
    assert "image/svg+xml" in result["outputs"][1]["data"]
