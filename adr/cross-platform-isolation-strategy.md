# Architecture Decision Record: Cross-Platform Isolation Strategy

## Status
Proposed

## Date
2025-04-18

## Context
The CodeBox-AI project currently relies on Docker for isolation and execution of Python code. This dependency creates friction for users, particularly on Windows where Docker requires enabling Hyper-V (which is unavailable on Windows Home editions) and on macOS where Docker Desktop installation is required. We need a solution that:

1. Minimizes prerequisites for users
2. Maintains strong security isolation
3. Works consistently across platforms (Windows, macOS, Linux)
4. Aligns with the project roadmap for supporting multiple execution backends

## Decision Drivers
* Security: Strong isolation is critical for running untrusted code
* User Experience: Minimal setup requirements for end users
* Performance: Reasonable startup and execution times
* Maintainability: Unified approach across platforms where possible
* Compatibility: Support for Windows Home edition and all macOS versions

## Considered Options

### Option 1: Continue with Docker
* Pros: Proven solution, already implemented, strong isolation
* Cons: High setup overhead, unavailable on Windows Home, requires Hyper-V

### Option 2: Process-Based Isolation
* Pros: No prerequisites, works everywhere
* Cons: Weak security boundaries, difficult to enforce resource limits

### Option 3: Platform-Specific Solutions
* Pros: Uses best available native technology on each platform
* Cons: Inconsistent implementation, varying security levels

### Option 4: Virtualized Podman (Selected)
* Pros: Consistent approach, strong isolation, works on Windows Home
* Cons: Requires lightweight VM setup (WSL2/Lima), but minimizes other requirements

## Decision
We will implement a unified approach using lightweight virtual machines with Podman:

1. On Windows: Use WSL2 as the VM layer with Podman installed inside
2. On macOS: Use Lima as the VM layer with Podman installed inside
3. On Linux: Use Podman directly if available

This provides container-level isolation without requiring Docker, and follows a consistent architectural pattern across platforms.

## Implementation Details

### Core Architecture
We will implement a unified `VirtualizedPodmanBackend` class with platform-specific setup:

```
┌─────────────────┐      ┌───────────────────┐
│                 │      │                   │
│  CodeBox-AI     │      │  CodeBox-AI       │
│  (Windows)      │      │  (macOS)          │
│                 │      │                   │
└────────┬────────┘      └──────────┬────────┘
         │                          │
         ▼                          ▼
┌────────────────┐      ┌───────────────────┐
│                │      │                   │
│     WSL2       │      │      Lima         │
│                │      │                   │
└────────┬───────┘      └──────────┬────────┘
         │                          │
         ▼                          ▼
┌────────────────┐      ┌───────────────────┐
│                │      │                   │
│    Podman      │      │     Podman        │
│                │      │                   │
└────────┬───────┘      └──────────┬────────┘
         │                          │
         ▼                          ▼
┌────────────────┐      ┌───────────────────┐
│                │      │                   │
│   Containers   │      │    Containers     │
│                │      │                   │
└────────────────┘      └───────────────────┘
```

### Key Components

1. **Backend Factory**
   - Creates the appropriate backend based on platform and available technologies
   - Attempts best available option first, with graceful fallbacks

2. **Virtualized Environment Management**
   - Windows: WSL2 setup and management
   - macOS: Lima setup and management
   - Both provide Linux environment for consistent container operations

3. **Podman Integration**
   - Handles installation of Podman inside VM if not present
   - Manages container lifecycle (create, start, exec, stop)
   - Provides consistent interface across platforms

4. **File Exchange**
   - Handles file transfer between host OS and VM environment
   - Manages code files, dependencies, and output

5. **Resource Controls**
   - Memory and CPU limits for containers
   - Process controls for code execution

### Implementation Strategy

1. **Abstraction Layer**
   - Create a common interface for all container backends
   - Allow runtime selection based on available technologies

2. **Platform Detection**
   - Detect operating system and available virtualization
   - Select appropriate backend implementation

3. **Graceful Degradation**
   - Fall back to less secure options if optimal solution unavailable
   - Inform users about recommended setup for better security

4. **User Experience**
   - Provide clear setup instructions for WSL2/Lima
   - Handle automatic setup of Podman inside VM

## User Requirements

### Windows
- Enable WSL2 (available on all Windows 10/11 editions)
- No Docker installation required
- No Hyper-V requirement

### macOS
- Install Lima via Homebrew: `brew install lima`
- No Docker installation required

### Linux
- Install Podman (or will use existing Docker if available)

## Technical Requirements

### Windows Components
- WSL2 for Linux environment
- Podman inside WSL2 for containerization

### macOS Components
- Lima for lightweight VM
- Podman inside Lima for containerization

### Common Setup Code
```python
def setup_podman_in_vm(self):
    # Check if podman is installed in VM
    result = self.execute_in_vm(["which", "podman"])
    
    if result.returncode != 0:
        # Install podman
        commands = [
            ["apt-get", "update"],
            ["apt-get", "install", "-y", "podman"]
        ]
        
        for cmd in commands:
            result = self.execute_in_vm(cmd)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to install podman: {result.stderr}")
```

## Alternatives Considered In Detail

### Native Sandboxing
- Windows Job Objects + macOS sandbox-exec
- Pros: No prerequisites
- Cons: Inconsistent implementation, weaker isolation

### WSL2+Docker and Lima+Docker
- Using Docker inside the VM environments
- Pros: Familiar Docker ecosystem
- Cons: Additional requirement of Docker installation

### Direct Process Isolation
- Running code directly with resource limits
- Pros: Simplest implementation, no prerequisites
- Cons: Least secure option, insufficient for untrusted code

## Implications

### Positive
- Works on all Windows editions including Home
- Provides strong container isolation
- Consistent architecture across platforms
- Aligns with Phase 2 roadmap goal of multiple execution backends

### Negative
- Small user setup requirement (WSL2/Lima installation)
- May have slightly slower startup compared to native execution
- Adds complexity to codebase for VM management

### Neutral
- Shifts dependency from Docker to WSL2/Lima + Podman
- Initial session creation may take longer but subsequent executions are fast

## Related Decisions
- Code validation remains important as secondary defense
- Resource limits will be applied at container level
- Session management and cleanup procedures need enhancement

## Open Questions
1. How to handle VM lifecycle (startup/shutdown) for optimal performance?
2. What's the optimal container image caching strategy?
3. How to implement proper error handling for VM/container failures?

## References
1. [WSL2 Documentation](https://docs.microsoft.com/en-us/windows/wsl/)
2. [Lima Project](https://github.com/lima-vm/lima)
3. [Podman Documentation](https://podman.io/docs)
4. [CodeBox-AI Roadmap](ROADMAP.md)
5. [Security Phase 1 Plan](SECURITY_P1.md)

## Appendix: sample code

```python
class VirtualizedPodmanBackend:
    """Container backend using Podman in a virtualized environment on both platforms"""
    
    def __init__(self):
        self.platform = platform.system()
        if self.platform == "Darwin":  # macOS
            self._setup_lima_environment()
            self.execute_in_vm = self._execute_in_lima
        elif self.platform == "Windows":
            self._setup_wsl_environment()
            self.execute_in_vm = self._execute_in_wsl
        else:
            # Direct execution on Linux
            self._setup_podman_linux()
            self.execute_in_vm = lambda cmd: subprocess.run(cmd, capture_output=True, text=True)
            
        # Set up Podman inside VM
        self._setup_podman_in_vm()
        self.containers = {}
    
    def _setup_lima_environment(self):
        """Set up Lima VM environment on macOS"""
        try:
            # Check if Lima is installed
            result = subprocess.run(["limactl", "version"], capture_output=True)
            if result.returncode != 0:
                raise RuntimeError("Lima not installed")
                
            # Check if our VM instance exists
            result = subprocess.run(["limactl", "list", "--format=json"], 
                                   capture_output=True, text=True)
            instances = json.loads(result.stdout)
            
            instance_name = "codebox-runtime"
            instance_exists = any(i["name"] == instance_name for i in instances)
            
            if not instance_exists:
                # Create a minimal Lima VM for our use
                config = {
                    "memory": "2GiB",
                    "cpus": 2,
                    "mounts": [{"location": "~", "writable": True}],
                    "images": [{"location": "https://cloud-images.ubuntu.com/minimal/releases/focal/release/ubuntu-20.04-minimal-cloudimg-amd64.img"}]
                }
                
                with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml') as f:
                    import yaml
                    yaml.dump(config, f)
                    f.flush()
                    subprocess.run(["limactl", "start", "--name", instance_name, f.name], check=True)
            
            self.vm_name = instance_name
            
        except FileNotFoundError:
            raise RuntimeError("Lima not installed. Install with: brew install lima")
    
    def _setup_wsl_environment(self):
        """Set up WSL environment on Windows"""
        try:
            # Check if WSL2 is available
            result = subprocess.run(["wsl", "--status"], capture_output=True, text=True)
            if "WSL 2" not in result.stdout:
                raise RuntimeError("WSL2 not available or not default version")
                
            # Ensure a Linux distribution is installed
            result = subprocess.run(["wsl", "-l", "-v"], capture_output=True, text=True)
            if "Ubuntu" not in result.stdout and "Debian" not in result.stdout:
                raise RuntimeError("No Linux distribution found in WSL")
                
        except FileNotFoundError:
            raise RuntimeError("WSL not installed. Install from Microsoft Store or enable the feature.")
    
    def _execute_in_lima(self, cmd):
        """Execute a command in Lima VM"""
        full_cmd = ["limactl", "shell", self.vm_name, "--"] + cmd
        return subprocess.run(full_cmd, capture_output=True, text=True)
    
    def _execute_in_wsl(self, cmd):
        """Execute a command in WSL"""
        full_cmd = ["wsl"] + cmd
        return subprocess.run(full_cmd, capture_output=True, text=True)
    
    def _setup_podman_in_vm(self):
        """Set up Podman inside the VM environment"""
        # Check if podman is installed in VM
        result = self.execute_in_vm(["which", "podman"])
        
        if result.returncode != 0:
            # Install podman
            if self.platform == "Darwin":  # Lima uses Ubuntu
                commands = [
                    ["apt-get", "update"],
                    ["apt-get", "install", "-y", "podman"]
                ]
            else:  # WSL likely uses Ubuntu
                commands = [
                    ["sudo", "apt-get", "update"],
                    ["sudo", "apt-get", "install", "-y", "podman"]
                ]
            
            for cmd in commands:
                result = self.execute_in_vm(cmd)
                if result.returncode != 0:
                    raise RuntimeError(f"Failed to install podman: {result.stderr}")
    
    def start_container(self, container_id, image="python:3.9-slim"):
        """Start a container using Podman in VM"""
        container_name = f"codebox-{container_id}"
        
        # Pull the image
        self.execute_in_vm(["podman", "pull", image])
        
        # Create temp directory in VM
        vm_workspace = f"/tmp/codebox-{container_id}"
        self.execute_in_vm(["mkdir", "-p", vm_workspace])
        
        # Start container
        cmd = [
            "podman", "run",
            "--name", container_name,
            "-d",
            "--rm",
            "-v", f"{vm_workspace}:/workspace",
            "--memory", "512m",
            image,
            "sleep", "infinity"
        ]
        
        result = self.execute_in_vm(cmd)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to start container: {result.stderr}")
        
        self.containers[container_id] = {
            "name": container_name,
            "workspace": vm_workspace
        }
        
        return container_id
    
    def install_dependencies(self, container_id, dependencies):
        """Install Python dependencies in the container"""
        if not dependencies:
            return
            
        container_name = self.containers[container_id]["name"]
        
        # Install dependencies
        cmd = ["podman", "exec", container_name, "pip", "install"] + dependencies
        result = self.execute_in_vm(cmd)
        
        if result.returncode != 0:
            raise ValueError(f"Failed to install dependencies: {result.stderr}")
    
    def execute_code(self, container_id, code, timeout=30):
        """Execute Python code in the container"""
        container_name = self.containers[container_id]["name"]
        workspace = self.containers[container_id]["workspace"]
        
        # Write code to file in VM
        with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        # Get path in VM format
        if self.platform == "Darwin":
            # Copy file to VM
            subprocess.run(["limactl", "copy", temp_file, f"{self.vm_name}:{workspace}/code.py"])
        else:  # Windows
            # Get WSL path and copy
            wsl_path = f"/mnt/c/{temp_file.replace(':', '').replace('\\', '/')}"
            self.execute_in_vm(["cp", wsl_path, f"{workspace}/code.py"])
        
        # Execute code
        cmd = ["podman", "exec", container_name, "python", "/workspace/code.py"]
        result = self.execute_in_vm(cmd)
        
        # Clean up
        try:
            os.unlink(temp_file)
        except:
            pass
        
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    
    def stop_container(self, container_id):
        """Stop and remove the container"""
        if container_id not in self.containers:
            return
            
        container_name = self.containers[container_id]["name"]
        workspace = self.containers[container_id]["workspace"]
        
        # Stop container
        self.execute_in_vm(["podman", "stop", container_name])
        
        # Clean up workspace
        self.execute_in_vm(["rm", "-rf", workspace])
        
        del self.containers[container_id]
```
