#!/usr/bin/env python3
"""
🐳 Docker Learning Playground

An interactive command-line tool for learning Docker concepts through hands-on experiments.
This playground provides safe, guided experiments that teach Docker fundamentals progressively.

Usage: python docker_playground.py [experiment_name]
"""

import subprocess
import sys
import time
import json
import os
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import argparse
from datetime import datetime

class DockerPlayground:
    """Interactive Docker learning playground."""

    def __init__(self):
        self.experiments = {}
        self.temp_dir = Path(tempfile.mkdtemp(prefix="docker_playground_"))
        self.session_log = []

        # Initialize experiments
        self._setup_experiments()

        print("🐳 Docker Learning Playground Initialized!")
        print(f"📁 Working directory: {self.temp_dir}")
        print("🧹 Cleanup will happen automatically on exit")

    def _setup_experiments(self):
        """Initialize all available experiments."""

        self.experiments = {
            "hello": {
                "name": "Hello Docker World",
                "description": "Your first Docker container - the classic hello world",
                "difficulty": "Beginner",
                "duration": "2 minutes",
                "function": self.experiment_hello_world
            },
            "images": {
                "name": "Image Exploration",
                "description": "Learn about Docker images, layers, and image management",
                "difficulty": "Beginner",
                "duration": "5 minutes",
                "function": self.experiment_image_exploration
            },
            "build": {
                "name": "Building Your First Image",
                "description": "Create a custom Docker image from scratch with a Dockerfile",
                "difficulty": "Intermediate",
                "duration": "10 minutes",
                "function": self.experiment_build_image
            },
            "volumes": {
                "name": "Data Persistence",
                "description": "Explore Docker volumes and data persistence strategies",
                "difficulty": "Intermediate",
                "duration": "8 minutes",
                "function": self.experiment_volumes
            },
            "networking": {
                "name": "Container Networking",
                "description": "Understand Docker networking and container communication",
                "difficulty": "Intermediate",
                "duration": "12 minutes",
                "function": self.experiment_networking
            },
            "compose": {
                "name": "Multi-Container Apps",
                "description": "Use Docker Compose to orchestrate multiple containers",
                "difficulty": "Advanced",
                "duration": "15 minutes",
                "function": self.experiment_compose
            },
            "monitoring": {
                "name": "Container Monitoring",
                "description": "Monitor container performance and resource usage",
                "difficulty": "Advanced",
                "duration": "10 minutes",
                "function": self.experiment_monitoring
            },
            "security": {
                "name": "Container Security",
                "description": "Learn Docker security best practices hands-on",
                "difficulty": "Advanced",
                "duration": "12 minutes",
                "function": self.experiment_security
            }
        }

    def run_command(self, cmd: str, capture_output: bool = True,
                   show_command: bool = True) -> Tuple[int, str, str]:
        """Run a shell command and return results."""
        if show_command:
            print(f"🔧 Running: {cmd}")

        self.session_log.append({
            "timestamp": datetime.now().isoformat(),
            "command": cmd,
            "type": "command"
        })

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=capture_output,
                text=True,
                cwd=self.temp_dir,
                timeout=60
            )

            if capture_output:
                if result.returncode == 0:
                    if result.stdout.strip():
                        print(f"✅ Output: {result.stdout.strip()}")
                else:
                    print(f"❌ Error (exit code {result.returncode}): {result.stderr.strip()}")

                return result.returncode, result.stdout, result.stderr
            else:
                return result.returncode, "", ""

        except subprocess.TimeoutExpired:
            print("⏰ Command timed out after 60 seconds")
            return 1, "", "Timeout"
        except Exception as e:
            print(f"💥 Exception: {e}")
            return 1, "", str(e)

    def wait_for_input(self, message: str = "Press Enter to continue..."):
        """Wait for user input before proceeding."""
        print(f"\n⏸️  {message}")
        input()

    def create_file(self, filename: str, content: str, description: str = ""):
        """Create a file in the playground directory."""
        file_path = self.temp_dir / filename
        with open(file_path, 'w') as f:
            f.write(content)

        if description:
            print(f"📝 Created {filename}: {description}")
        else:
            print(f"📝 Created {filename}")

        return file_path

    def show_file(self, filename: str):
        """Display file contents with syntax highlighting."""
        file_path = self.temp_dir / filename
        if file_path.exists():
            print(f"\n📄 Contents of {filename}:")
            print("─" * 50)
            with open(file_path, 'r') as f:
                for i, line in enumerate(f, 1):
                    print(f"{i:3}: {line.rstrip()}")
            print("─" * 50)
        else:
            print(f"❌ File {filename} not found")

    def experiment_hello_world(self):
        """Experiment 1: Hello Docker World."""
        print("🌟 Experiment: Hello Docker World")
        print("=" * 50)
        print("🎯 Learning Goals:")
        print("   • Run your first Docker container")
        print("   • Understand container lifecycle")
        print("   • Learn basic Docker commands")
        print()

        # Step 1: Check Docker installation
        print("📋 Step 1: Verify Docker Installation")
        self.run_command("docker --version")
        self.wait_for_input()

        # Step 2: Run hello-world container
        print("\n📋 Step 2: Run the Official Hello World Container")
        self.run_command("docker run hello-world")

        print("\n💡 What happened?")
        print("   1. Docker looked for 'hello-world' image locally")
        print("   2. Didn't find it, so pulled from Docker Hub")
        print("   3. Created and ran a container from the image")
        print("   4. Container executed, printed message, and exited")

        self.wait_for_input()

        # Step 3: List containers
        print("\n📋 Step 3: See Container History")
        self.run_command("docker ps -a")

        print("\n💡 Notice:")
        print("   • Container has STATUS 'Exited'")
        print("   • Each container gets a unique ID and name")
        print("   • Containers persist after exit (until removed)")

        self.wait_for_input()

        # Step 4: Run interactive container
        print("\n📋 Step 4: Run an Interactive Container")
        print("🎮 Let's run Ubuntu interactively!")
        print("   Type 'exit' to leave the container when prompted")

        self.wait_for_input("Press Enter to start interactive Ubuntu container...")
        self.run_command("docker run -it ubuntu:20.04 /bin/bash", capture_output=False)

        print("\n🎉 Congratulations! You've completed your first Docker experiment!")
        print("📚 Key concepts learned:")
        print("   • docker run - Creates and starts containers")
        print("   • -it flags - Interactive terminal")
        print("   • docker ps - Lists containers")
        print("   • Container lifecycle")

    def experiment_image_exploration(self):
        """Experiment 2: Image Exploration."""
        print("🔍 Experiment: Image Exploration")
        print("=" * 50)
        print("🎯 Learning Goals:")
        print("   • Understand Docker images vs containers")
        print("   • Explore image layers and history")
        print("   • Learn image management commands")
        print()

        # Step 1: List current images
        print("📋 Step 1: List Downloaded Images")
        self.run_command("docker images")

        print("\n💡 Each image has:")
        print("   • Repository name (e.g., ubuntu, hello-world)")
        print("   • Tag (version, like 20.04, latest)")
        print("   • Image ID (unique identifier)")
        print("   • Size on disk")

        self.wait_for_input()

        # Step 2: Pull a specific image
        print("\n📋 Step 2: Pull a Specific Image")
        print("🚀 Downloading nginx web server...")
        self.run_command("docker pull nginx:alpine")

        print("\n💡 What happened?")
        print("   • Downloaded nginx with 'alpine' tag")
        print("   • Alpine = smaller, security-focused Linux distribution")
        print("   • Images are pulled in layers for efficiency")

        self.wait_for_input()

        # Step 3: Inspect image details
        print("\n📋 Step 3: Inspect Image Details")
        self.run_command("docker inspect nginx:alpine")

        print("\n💡 Inspection reveals:")
        print("   • Image configuration")
        print("   • Environment variables")
        print("   • Default command")
        print("   • Port exposures")

        self.wait_for_input()

        # Step 4: Image history (layers)
        print("\n📋 Step 4: Examine Image Layers")
        self.run_command("docker history nginx:alpine")

        print("\n💡 Image Layers:")
        print("   • Each line is a layer in the image")
        print("   • Layers are cached and reusable")
        print("   • Smaller layers = faster downloads")

        self.wait_for_input()

        # Step 5: Size comparison
        print("\n📋 Step 5: Compare Image Sizes")
        self.run_command("docker images --format 'table {{.Repository}}\\t{{.Tag}}\\t{{.Size}}'")

        print("\n🎉 Image exploration complete!")
        print("📚 Key concepts learned:")
        print("   • docker images - List local images")
        print("   • docker pull - Download images")
        print("   • docker inspect - Detailed image info")
        print("   • docker history - Show image layers")
        print("   • Image layers and caching")

    def experiment_build_image(self):
        """Experiment 3: Building Your First Image."""
        print("🏗️ Experiment: Building Your First Image")
        print("=" * 50)
        print("🎯 Learning Goals:")
        print("   • Create a Dockerfile")
        print("   • Build a custom Docker image")
        print("   • Understand build context and layers")
        print("   • Tag and run your custom image")
        print()

        # Step 1: Create application files
        print("📋 Step 1: Create a Simple Web Application")

        # Create HTML file
        html_content = """<!DOCTYPE html>
<html>
<head>
    <title>My Docker App</title>
    <style>
        body { font-family: Arial; text-align: center; margin-top: 50px; }
        .container { max-width: 600px; margin: 0 auto; }
        .docker { color: #2496ED; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🐳 Welcome to My <span class="docker">Docker</span> App!</h1>
        <p>This web page is served from inside a Docker container!</p>
        <p>Built on: <strong>{{ build_date }}</strong></p>
        <p>Container ID: <strong>{{ container_id }}</strong></p>
    </div>
</body>
</html>"""

        self.create_file("index.html", html_content, "Simple HTML page")

        # Create Python web server
        python_content = """#!/usr/bin/env python3
import http.server
import socketserver
import os
import socket
from datetime import datetime

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()

            # Read and customize HTML
            with open('index.html', 'r') as f:
                html = f.read()

            # Replace placeholders
            html = html.replace('{{ build_date }}', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            html = html.replace('{{ container_id }}', socket.gethostname())

            self.wfile.write(html.encode())
        else:
            super().do_GET()

PORT = 8080
print(f"🌐 Starting web server on port {PORT}")
print(f"🏠 Container hostname: {socket.gethostname()}")

with socketserver.TCPServer(("", PORT), CustomHandler) as httpd:
    print(f"📡 Server running at http://localhost:{PORT}")
    httpd.serve_forever()
"""

        self.create_file("server.py", python_content, "Python web server")

        self.wait_for_input()

        # Step 2: Create Dockerfile
        print("\n📋 Step 2: Create a Dockerfile")

        dockerfile_content = """# My First Dockerfile
# Use Python 3.11 on Alpine Linux (small and secure)
FROM python:3.11-alpine

# Set working directory inside container
WORKDIR /app

# Copy application files
COPY index.html .
COPY server.py .

# Make server.py executable
RUN chmod +x server.py

# Expose port 8080
EXPOSE 8080

# Add labels for metadata
LABEL maintainer="Docker Learning Playground"
LABEL description="My first custom Docker image"
LABEL version="1.0"

# Run the web server when container starts
CMD ["python", "server.py"]
"""

        self.create_file("Dockerfile", dockerfile_content, "Instructions for building our image")

        # Show the Dockerfile
        self.show_file("Dockerfile")

        print("\n💡 Dockerfile Explanation:")
        print("   • FROM: Base image to start with")
        print("   • WORKDIR: Working directory inside container")
        print("   • COPY: Copy files from host to container")
        print("   • RUN: Execute commands during build")
        print("   • EXPOSE: Document which port the app uses")
        print("   • CMD: Default command when container starts")

        self.wait_for_input()

        # Step 3: Build the image
        print("\n📋 Step 3: Build the Docker Image")
        print("🔨 Building image 'my-web-app:v1.0'...")

        self.run_command("docker build -t my-web-app:v1.0 .")

        print("\n💡 Build Process:")
        print("   • Docker reads Dockerfile instructions")
        print("   • Each instruction creates a new layer")
        print("   • Layers are cached for faster rebuilds")
        print("   • Final image gets tagged 'my-web-app:v1.0'")

        self.wait_for_input()

        # Step 4: List images to see our new image
        print("\n📋 Step 4: Verify Our New Image")
        self.run_command("docker images | grep my-web-app")

        self.wait_for_input()

        # Step 5: Run the container
        print("\n📋 Step 5: Run Our Custom Container")
        print("🚀 Starting web server container...")

        self.run_command("docker run -d -p 8080:8080 --name my-web-container my-web-app:v1.0")

        print("\n💡 Command breakdown:")
        print("   • -d: Run in background (detached)")
        print("   • -p 8080:8080: Map port 8080 (host:container)")
        print("   • --name: Give container a friendly name")

        # Wait a moment for startup
        time.sleep(2)

        # Step 6: Test the application
        print("\n📋 Step 6: Test Our Web Application")
        print("🌐 Testing web server...")

        self.run_command("curl -s http://localhost:8080 | head -10")

        print("\n🎯 Try opening http://localhost:8080 in your browser!")
        self.wait_for_input("Press Enter after testing in browser...")

        # Step 7: View container logs
        print("\n📋 Step 7: Check Container Logs")
        self.run_command("docker logs my-web-container")

        # Step 8: Cleanup
        print("\n📋 Step 8: Cleanup")
        print("🧹 Stopping and removing container...")
        self.run_command("docker stop my-web-container")
        self.run_command("docker rm my-web-container")

        print("\n🎉 Congratulations! You built and ran your first custom Docker image!")
        print("📚 Key concepts learned:")
        print("   • Dockerfile syntax and instructions")
        print("   • docker build - Create images from Dockerfile")
        print("   • Build context and layer caching")
        print("   • Port mapping with -p")
        print("   • Container naming with --name")
        print("   • Background containers with -d")

    def experiment_volumes(self):
        """Experiment 4: Data Persistence with Volumes."""
        print("💾 Experiment: Data Persistence with Volumes")
        print("=" * 50)
        print("🎯 Learning Goals:")
        print("   • Understand container data persistence")
        print("   • Learn about different volume types")
        print("   • Share data between containers and host")
        print("   • Explore volume management")
        print()

        # Step 1: Demonstrate ephemeral nature
        print("📋 Step 1: Container Data is Ephemeral (By Default)")
        print("🔬 Let's prove containers lose data when removed...")

        # Create and write to a file in container
        print("\n🗃️ Creating a file inside a container...")
        self.run_command("docker run --name temp-container ubuntu:20.04 sh -c 'echo \"Important data!\" > /tmp/myfile.txt && cat /tmp/myfile.txt'")

        # Remove container
        print("\n🗑️ Removing the container...")
        self.run_command("docker rm temp-container")

        # Try to find the data (it's gone!)
        print("\n🔍 Data is lost forever - containers are ephemeral!")

        self.wait_for_input()

        # Step 2: Bind Mounts
        print("\n📋 Step 2: Bind Mounts - Share Host Directories")

        # Create host directory with data
        host_data = self.temp_dir / "shared_data"
        host_data.mkdir()

        sample_file = host_data / "host_file.txt"
        with open(sample_file, 'w') as f:
            f.write("This file exists on the host machine!\n")

        print(f"📁 Created host directory: {host_data}")
        print(f"📄 Created file: {sample_file}")

        # Mount host directory into container
        print("\n🔗 Mounting host directory into container...")
        self.run_command(f"docker run --rm -v {host_data}:/data ubuntu:20.04 sh -c 'ls -la /data && cat /data/host_file.txt'")

        # Modify file from container
        print("\n✏️ Modifying file from inside container...")
        self.run_command(f"docker run --rm -v {host_data}:/data ubuntu:20.04 sh -c 'echo \"Modified from container!\" >> /data/host_file.txt'")

        # Verify changes on host
        print("\n🔍 Checking changes on host:")
        with open(sample_file, 'r') as f:
            print(f.read())

        print("💡 Bind mounts provide bidirectional data sharing!")

        self.wait_for_input()

        # Step 3: Named Volumes
        print("\n📋 Step 3: Named Volumes - Docker-Managed Storage")

        # Create named volume
        print("🏗️ Creating a named volume...")
        self.run_command("docker volume create my-data-volume")

        # List volumes
        self.run_command("docker volume ls")

        # Use volume in container
        print("\n📝 Writing data to named volume...")
        self.run_command("docker run --rm -v my-data-volume:/data ubuntu:20.04 sh -c 'echo \"Persistent data in named volume!\" > /data/persistent.txt'")

        # Read data from another container
        print("\n📖 Reading data from another container...")
        self.run_command("docker run --rm -v my-data-volume:/data ubuntu:20.04 cat /data/persistent.txt")

        print("💡 Named volumes persist independently of containers!")

        self.wait_for_input()

        # Step 4: Volume inspection
        print("\n📋 Step 4: Inspect Volume Details")
        self.run_command("docker volume inspect my-data-volume")

        print("\n💡 Volume details show:")
        print("   • Driver (usually 'local')")
        print("   • Mountpoint (where Docker stores the data)")
        print("   • Scope and metadata")

        self.wait_for_input()

        # Step 5: Practical example - Database persistence
        print("\n📋 Step 5: Practical Example - Persistent Database")
        print("🗄️ Running PostgreSQL with persistent data...")

        # Start PostgreSQL with named volume
        self.run_command("docker run -d --name postgres-demo -e POSTGRES_PASSWORD=mypassword -v postgres-data:/var/lib/postgresql/data postgres:13-alpine")

        # Wait for startup
        print("⏱️ Waiting for PostgreSQL to start...")
        time.sleep(10)

        # Create a table and insert data
        print("\n📝 Creating database table...")
        self.run_command("docker exec postgres-demo psql -U postgres -c \"CREATE TABLE users (id SERIAL, name TEXT);\"")
        self.run_command("docker exec postgres-demo psql -U postgres -c \"INSERT INTO users (name) VALUES ('Alice'), ('Bob');\"")

        # Query data
        print("\n📊 Querying data...")
        self.run_command("docker exec postgres-demo psql -U postgres -c \"SELECT * FROM users;\"")

        # Stop and remove container
        print("\n🛑 Stopping and removing container...")
        self.run_command("docker stop postgres-demo")
        self.run_command("docker rm postgres-demo")

        # Start new container with same volume
        print("\n🔄 Starting new container with same volume...")
        self.run_command("docker run -d --name postgres-demo2 -e POSTGRES_PASSWORD=mypassword -v postgres-data:/var/lib/postgresql/data postgres:13-alpine")

        time.sleep(10)

        # Verify data persisted
        print("\n✅ Verifying data persisted...")
        self.run_command("docker exec postgres-demo2 psql -U postgres -c \"SELECT * FROM users;\"")

        # Cleanup
        print("\n🧹 Cleaning up...")
        self.run_command("docker stop postgres-demo2")
        self.run_command("docker rm postgres-demo2")
        self.run_command("docker volume rm postgres-data")
        self.run_command("docker volume rm my-data-volume")

        print("\n🎉 Volume experiment complete!")
        print("📚 Key concepts learned:")
        print("   • Container data is ephemeral by default")
        print("   • Bind mounts: -v /host/path:/container/path")
        print("   • Named volumes: docker volume create")
        print("   • Volume persistence across container lifecycles")
        print("   • docker volume commands")

    def experiment_networking(self):
        """Experiment 5: Container Networking."""
        print("🌐 Experiment: Container Networking")
        print("=" * 50)
        print("🎯 Learning Goals:")
        print("   • Understand Docker networking concepts")
        print("   • Create custom networks")
        print("   • Enable container-to-container communication")
        print("   • Learn about network isolation")
        print()

        # Step 1: Default networking
        print("📋 Step 1: Explore Default Docker Networking")

        # List networks
        print("🔍 Default Docker networks:")
        self.run_command("docker network ls")

        print("\n💡 Default networks:")
        print("   • bridge: Default network for containers")
        print("   • host: Use host's network stack")
        print("   • none: No networking")

        self.wait_for_input()

        # Step 2: Container on default network
        print("\n📋 Step 2: Container on Default Network")

        # Start nginx container
        self.run_command("docker run -d --name web1 -p 8081:80 nginx:alpine")

        # Inspect container network
        print("\n🔍 Inspecting container network settings...")
        self.run_command("docker inspect web1 --format '{{json .NetworkSettings.Networks}}' | python3 -m json.tool")

        # Test connectivity
        print("\n🌐 Testing web server...")
        time.sleep(2)
        self.run_command("curl -s http://localhost:8081 | head -3")

        self.wait_for_input()

        # Step 3: Create custom network
        print("\n📋 Step 3: Create Custom Network")

        # Create custom bridge network
        print("🏗️ Creating custom network...")
        self.run_command("docker network create --driver bridge my-app-network")

        # Inspect network
        self.run_command("docker network inspect my-app-network")

        print("\n💡 Custom networks provide:")
        print("   • Better isolation")
        print("   • Built-in DNS resolution")
        print("   • Custom IP ranges")

        self.wait_for_input()

        # Step 4: Multi-container communication
        print("\n📋 Step 4: Multi-Container Communication")

        # Start database on custom network
        print("🗄️ Starting database container...")
        self.run_command("docker run -d --name mydb --network my-app-network -e POSTGRES_PASSWORD=secret postgres:13-alpine")

        # Start web app on custom network
        print("🌐 Starting web application...")
        web_app_dockerfile = """FROM python:3.11-alpine
RUN pip install psycopg2-binary
COPY app.py /app.py
CMD ["python", "/app.py"]
"""

        app_code = """#!/usr/bin/env python3
import psycopg2
import time
import sys

def test_db_connection():
    try:
        # Note: using 'mydb' as hostname - Docker DNS resolution!
        conn = psycopg2.connect(
            host="mydb",
            database="postgres",
            user="postgres",
            password="secret"
        )
        print("✅ Successfully connected to database!")

        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"📊 Database version: {version[0]}")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("🔗 Testing database connection...")
    time.sleep(5)  # Wait for database to be ready
    test_db_connection()
    print("✅ Web app started successfully!")

    # Keep container running
    while True:
        time.sleep(30)
        print("📡 Web app is running...")
"""

        # Create application files
        self.create_file("app.py", app_code)
        self.create_file("Dockerfile.webapp", web_app_dockerfile)

        # Build web app image
        print("\n🔨 Building web application image...")
        self.run_command("docker build -f Dockerfile.webapp -t my-web-app .")

        # Wait for database to be ready
        print("\n⏱️ Waiting for database to be ready...")
        time.sleep(10)

        # Run web app on same network
        self.run_command("docker run -d --name webapp --network my-app-network my-web-app")

        # Check web app logs
        print("\n📋 Checking web app connection...")
        time.sleep(8)
        self.run_command("docker logs webapp")

        self.wait_for_input()

        # Step 5: Network isolation demonstration
        print("\n📋 Step 5: Network Isolation")

        # Try connecting from default network (should fail)
        print("🚫 Testing isolation - this should fail...")
        self.run_command("docker run --rm alpine ping -c 3 mydb", capture_output=True)

        print("💡 Containers on different networks cannot communicate!")

        # Show network connectivity
        print("\n🔍 Showing network connectivity...")
        self.run_command("docker network inspect my-app-network --format '{{json .Containers}}' | python3 -m json.tool")

        self.wait_for_input()

        # Step 6: Connect container to multiple networks
        print("\n📋 Step 6: Multi-Network Containers")

        # Connect web1 (from default network) to custom network
        print("🔗 Connecting web1 to custom network...")
        self.run_command("docker network connect my-app-network web1")

        # Now web1 can access database
        print("\n🧪 Testing cross-network connectivity...")
        self.run_command("docker exec web1 ping -c 3 mydb")

        print("✅ Container is now on both networks!")

        # Step 7: Cleanup
        print("\n📋 Step 7: Cleanup")
        print("🧹 Removing containers and networks...")

        self.run_command("docker stop webapp mydb web1")
        self.run_command("docker rm webapp mydb web1")
        self.run_command("docker network rm my-app-network")
        self.run_command("docker rmi my-web-app")

        print("\n🎉 Networking experiment complete!")
        print("📚 Key concepts learned:")
        print("   • docker network create/ls/inspect")
        print("   • Custom networks provide DNS resolution")
        print("   • Network isolation and security")
        print("   • --network flag for container networking")
        print("   • Multi-network containers")

    def experiment_compose(self):
        """Experiment 6: Multi-Container Apps with Docker Compose."""
        print("🎼 Experiment: Multi-Container Apps with Docker Compose")
        print("=" * 50)
        print("🎯 Learning Goals:")
        print("   • Understand Docker Compose concepts")
        print("   • Define multi-container applications")
        print("   • Manage application lifecycle")
        print("   • Use environment variables and volumes")
        print()

        # Check if docker-compose is available
        result, _, _ = self.run_command("docker-compose --version", capture_output=True, show_command=False)
        if result != 0:
            # Try docker compose (newer syntax)
            result, _, _ = self.run_command("docker compose version", capture_output=True, show_command=False)
            if result != 0:
                print("❌ Docker Compose not found. Please install Docker Compose first.")
                return
            else:
                compose_cmd = "docker compose"
        else:
            compose_cmd = "docker-compose"

        print(f"✅ Using: {compose_cmd}")

        # Step 1: Create application structure
        print("\n📋 Step 1: Create Multi-Container Application")
        print("🏗️ Building a complete web application stack...")

        # Create Flask web application
        flask_app = """from flask import Flask, request, jsonify
import psycopg2
import redis
import os
import json
from datetime import datetime

app = Flask(__name__)

# Database connection
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'db'),
        database=os.getenv('POSTGRES_DB', 'webapp'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', 'secret')
    )

# Redis connection
def get_redis():
    return redis.Redis(
        host=os.getenv('REDIS_HOST', 'redis'),
        port=6379,
        decode_responses=True
    )

@app.route('/')
def hello():
    return '''
    <h1>🐳 Multi-Container Web App</h1>
    <p>This app uses:</p>
    <ul>
        <li>🐍 Python Flask (Web Server)</li>
        <li>🗄️ PostgreSQL (Database)</li>
        <li>⚡ Redis (Cache)</li>
    </ul>
    <p><a href="/api/status">Check API Status</a></p>
    <p><a href="/api/visits">View Visit Counter</a></p>
    '''

@app.route('/api/status')
def status():
    try:
        # Test database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        db_status = "✅ Connected"
    except Exception as e:
        db_status = f"❌ Error: {e}"

    try:
        # Test Redis
        r = get_redis()
        r.ping()
        redis_status = "✅ Connected"
    except Exception as e:
        redis_status = f"❌ Error: {e}"

    return jsonify({
        "timestamp": datetime.now().isoformat(),
        "database": db_status,
        "redis": redis_status,
        "hostname": os.uname().nodename
    })

@app.route('/api/visits')
def visits():
    try:
        r = get_redis()
        visit_count = r.incr('visit_counter')
        return jsonify({
            "visits": visit_count,
            "message": f"This page has been visited {visit_count} times!"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
"""

        self.create_file("app.py", flask_app, "Flask web application")

        # Create requirements.txt
        requirements = """Flask==2.3.3
psycopg2-binary==2.9.7
redis==4.6.0
"""
        self.create_file("requirements.txt", requirements, "Python dependencies")

        # Create Dockerfile for web app
        dockerfile = """FROM python:3.11-alpine

# Install PostgreSQL client dependencies
RUN apk add --no-cache postgresql-dev gcc musl-dev

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app.py .

EXPOSE 5000

CMD ["python", "app.py"]
"""
        self.create_file("Dockerfile", dockerfile, "Web app container definition")

        self.wait_for_input()

        # Step 2: Create Docker Compose file
        print("\n📋 Step 2: Create Docker Compose Configuration")

        compose_content = """version: '3.8'

services:
  # Web application
  web:
    build: .
    ports:
      - "5000:5000"
    environment:
      - POSTGRES_HOST=db
      - POSTGRES_DB=webapp
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=secret
      - REDIS_HOST=redis
    depends_on:
      - db
      - redis
    volumes:
      - .:/app  # Live code reloading for development
    networks:
      - app-network

  # PostgreSQL database
  db:
    image: postgres:13-alpine
    environment:
      - POSTGRES_DB=webapp
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=secret
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    networks:
      - app-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 30s
      timeout: 10s
      retries: 5

  # Redis cache
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    networks:
      - app-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 5

  # Nginx reverse proxy
  nginx:
    image: nginx:alpine
    ports:
      - "8080:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - web
    networks:
      - app-network

# Named volumes for data persistence
volumes:
  postgres_data:
  redis_data:

# Custom network
networks:
  app-network:
    driver: bridge
"""

        self.create_file("docker-compose.yml", compose_content, "Multi-container application definition")

        # Create database initialization script
        init_sql = """-- Database initialization
CREATE TABLE IF NOT EXISTS app_info (
    id SERIAL PRIMARY KEY,
    key VARCHAR(50) UNIQUE,
    value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO app_info (key, value) VALUES
    ('app_name', 'Docker Compose Demo'),
    ('version', '1.0.0'),
    ('author', 'Docker Learning Playground')
ON CONFLICT (key) DO NOTHING;
"""
        self.create_file("init.sql", init_sql, "Database initialization script")

        # Create nginx configuration
        nginx_conf = """events {
    worker_connections 1024;
}

http {
    upstream webapp {
        server web:5000;
    }

    server {
        listen 80;

        location / {
            proxy_pass http://webapp;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
}
"""
        self.create_file("nginx.conf", nginx_conf, "Nginx reverse proxy configuration")

        self.wait_for_input()

        # Step 3: Start the application stack
        print("\n📋 Step 3: Launch the Application Stack")
        print("🚀 Starting all services with Docker Compose...")

        self.run_command(f"{compose_cmd} up -d")

        # Wait for services to be ready
        print("\n⏱️ Waiting for services to be ready...")
        time.sleep(15)

        # Check service status
        print("\n📊 Checking service status...")
        self.run_command(f"{compose_cmd} ps")

        self.wait_for_input()

        # Step 4: Test the application
        print("\n📋 Step 4: Test the Multi-Container Application")

        # Test direct web app
        print("🌐 Testing web application directly...")
        self.run_command("curl -s http://localhost:5000/api/status | python3 -m json.tool")

        # Test through nginx proxy
        print("\n🔄 Testing through Nginx proxy...")
        self.run_command("curl -s http://localhost:8080/api/status | python3 -m json.tool")

        # Test visit counter
        print("\n📊 Testing visit counter...")
        for i in range(3):
            self.run_command("curl -s http://localhost:8080/api/visits | python3 -m json.tool")

        self.wait_for_input()

        # Step 5: View logs
        print("\n📋 Step 5: Monitor Application Logs")
        print("📝 Web application logs:")
        self.run_command(f"{compose_cmd} logs web --tail 10")

        print("\n📝 Database logs:")
        self.run_command(f"{compose_cmd} logs db --tail 5")

        self.wait_for_input()

        # Step 6: Scale services
        print("\n📋 Step 6: Scale Services")
        print("📈 Scaling web service to 3 instances...")

        self.run_command(f"{compose_cmd} up -d --scale web=3")

        print("\n📊 Service status after scaling:")
        self.run_command(f"{compose_cmd} ps")

        self.wait_for_input()

        # Step 7: Environment management
        print("\n📋 Step 7: Environment Management")

        # Create production override
        prod_override = """version: '3.8'

services:
  web:
    environment:
      - FLASK_ENV=production
    volumes: []  # Remove development volume mount
    restart: unless-stopped

  db:
    restart: unless-stopped

  redis:
    restart: unless-stopped
    command: redis-server --appendonly yes  # Enable persistence

  nginx:
    restart: unless-stopped
"""

        self.create_file("docker-compose.prod.yml", prod_override, "Production overrides")

        print("📄 Created production configuration override")
        print("💡 Usage: docker-compose -f docker-compose.yml -f docker-compose.prod.yml up")

        self.wait_for_input()

        # Step 8: Cleanup
        print("\n📋 Step 8: Cleanup")
        print("🧹 Stopping and removing all services...")

        self.run_command(f"{compose_cmd} down -v")

        print("\n🎉 Docker Compose experiment complete!")
        print("📚 Key concepts learned:")
        print("   • docker-compose.yml file structure")
        print("   • Service definitions and dependencies")
        print("   • Networks and volumes in Compose")
        print("   • Environment variables and configuration")
        print("   • Service scaling with --scale")
        print("   • Configuration overrides for environments")
        print("   • docker-compose up/down/ps/logs commands")

    def experiment_monitoring(self):
        """Experiment 7: Container Monitoring."""
        print("📊 Experiment: Container Monitoring")
        print("=" * 50)
        print("🎯 Learning Goals:")
        print("   • Monitor container resource usage")
        print("   • Understand container metrics")
        print("   • Set up basic alerting")
        print("   • Use monitoring tools")
        print()

        # Step 1: Basic monitoring with docker stats
        print("📋 Step 1: Basic Resource Monitoring")

        # Start some containers to monitor
        print("🚀 Starting containers for monitoring...")
        self.run_command("docker run -d --name cpu-hog busybox sh -c 'while true; do :; done'")
        self.run_command("docker run -d --name memory-user nginx:alpine")
        self.run_command("docker run -d --name idle-container alpine sleep 300")

        time.sleep(2)

        # Show real-time stats
        print("\n📊 Real-time container statistics:")
        self.run_command("docker stats --no-stream")

        print("\n💡 Metrics explanation:")
        print("   • CPU %: Percentage of host CPU used")
        print("   • MEM USAGE: Physical memory used by container")
        print("   • MEM %: Percentage of available memory")
        print("   • NET I/O: Network bytes sent/received")
        print("   • BLOCK I/O: Disk bytes read/written")

        self.wait_for_input()

        # Step 2: Historical monitoring setup
        print("\n📋 Step 2: Set Up Monitoring Stack")

        # Create monitoring compose file
        monitoring_compose = """version: '3.8'

services:
  # cAdvisor - Container metrics collector
  cadvisor:
    image: gcr.io/cadvisor/cadvisor:latest
    container_name: cadvisor
    ports:
      - "8080:8080"
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
      - /dev/disk/:/dev/disk:ro
    privileged: true
    devices:
      - /dev/kmsg
    restart: unless-stopped

  # Simple metrics dashboard
  web-dashboard:
    image: nginx:alpine
    container_name: monitoring-dashboard
    ports:
      - "8081:80"
    volumes:
      - ./dashboard.html:/usr/share/nginx/html/index.html:ro
    restart: unless-stopped

  # Test application with varying load
  load-generator:
    image: alpine
    container_name: load-generator
    command: sh -c "while true; do dd if=/dev/zero of=/tmp/test bs=1M count=100 2>/dev/null && rm /tmp/test && sleep 5; done"
    restart: unless-stopped
"""

        self.create_file("monitoring-compose.yml", monitoring_compose, "Monitoring stack")

        # Create simple dashboard
        dashboard_html = """<!DOCTYPE html>
<html>
<head>
    <title>Container Monitoring Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .metric-box { border: 1px solid #ddd; padding: 15px; margin: 10px; border-radius: 5px; }
        .high { background-color: #ffebee; }
        .normal { background-color: #e8f5e8; }
        .container { display: flex; flex-wrap: wrap; }
        iframe { width: 100%; height: 600px; border: 1px solid #ddd; }
    </style>
    <script>
        function updateMetrics() {
            fetch('/api/metrics')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('metrics').innerHTML = JSON.stringify(data, null, 2);
                })
                .catch(err => console.error('Error:', err));
        }

        setInterval(updateMetrics, 5000);
        window.onload = updateMetrics;
    </script>
</head>
<body>
    <h1>🐳 Container Monitoring Dashboard</h1>

    <div class="container">
        <div class="metric-box">
            <h3>📊 cAdvisor (Detailed Metrics)</h3>
            <p>Access detailed container metrics at: <a href="http://localhost:8080" target="_blank">http://localhost:8080</a></p>
        </div>

        <div class="metric-box">
            <h3>⚡ Quick Commands</h3>
            <pre>
# View real-time stats
docker stats

# View container processes
docker exec CONTAINER top

# View container logs
docker logs CONTAINER

# Inspect container
docker inspect CONTAINER
            </pre>
        </div>
    </div>

    <h2>📈 Live Container Metrics</h2>
    <iframe src="http://localhost:8080/containers/" title="cAdvisor"></iframe>
</body>
</html>"""

        self.create_file("dashboard.html", dashboard_html, "Monitoring dashboard")

        # Start monitoring stack
        print("\n🚀 Starting monitoring stack...")
        self.run_command("docker-compose -f monitoring-compose.yml up -d")

        time.sleep(10)

        print("\n✅ Monitoring stack started!")
        print("🌐 Dashboard: http://localhost:8081")
        print("📊 cAdvisor: http://localhost:8080")

        self.wait_for_input("Press Enter after checking the monitoring dashboards...")

        # Step 3: Container health checks
        print("\n📋 Step 3: Container Health Checks")

        # Create container with health check
        healthcheck_dockerfile = """FROM nginx:alpine

# Add health check endpoint
RUN echo '<!DOCTYPE html><html><body><h1>OK</h1></body></html>' > /usr/share/nginx/html/health

# Configure health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \\
    CMD wget --no-verbose --tries=1 --spider http://localhost/health || exit 1
"""

        self.create_file("Dockerfile.health", healthcheck_dockerfile, "Container with health check")

        # Build and run healthy container
        self.run_command("docker build -f Dockerfile.health -t nginx-healthy .")
        self.run_command("docker run -d --name healthy-nginx nginx-healthy")

        # Wait and check health status
        print("\n⏱️ Waiting for health check...")
        time.sleep(10)

        self.run_command("docker ps --format 'table {{.Names}}\\t{{.Status}}'")

        print("\n💡 Health check status appears in the STATUS column!")

        self.wait_for_input()

        # Step 4: Monitoring alerts simulation
        print("\n📋 Step 4: Monitoring Alerts Simulation")

        # Create monitoring script
        monitoring_script = """#!/bin/bash
# Simple monitoring script

echo "🔍 Container Monitoring Report $(date)"
echo "=================================="

# Check container health
echo -e "\\n📊 Container Health Status:"
docker ps --format "table {{.Names}}\\t{{.Status}}" | grep -E "(healthy|unhealthy)" || echo "No health checks configured"

# Check resource usage
echo -e "\\n💾 High Memory Usage Containers:"
docker stats --no-stream --format "table {{.Container}}\\t{{.MemPerc}}" | awk 'NR>1 && $2+0 > 50 {print $0}' || echo "No high memory usage detected"

# Check failed containers
echo -e "\\n🚨 Failed/Exited Containers:"
docker ps -a --filter "status=exited" --format "table {{.Names}}\\t{{.Status}}" | head -10

# Check disk usage
echo -e "\\n💽 Docker Disk Usage:"
docker system df

echo -e "\\n✅ Monitoring check complete!"
"""

        self.create_file("monitor.sh", monitoring_script, "Simple monitoring script")

        # Make executable and run
        self.run_command("chmod +x monitor.sh")
        self.run_command("./monitor.sh")

        self.wait_for_input()

        # Step 5: Performance testing
        print("\n📋 Step 5: Performance Testing")

        # Stress test container
        print("🔥 Creating stressed container...")
        self.run_command("docker run -d --name stress-test --memory=100m progrium/stress --cpu 2 --io 1 --vm 1 --vm-bytes 50M --timeout 30s")

        print("\n📊 Monitoring stressed container:")
        time.sleep(5)
        self.run_command("docker stats stress-test --no-stream")

        # Wait for stress test to complete
        print("\n⏱️ Waiting for stress test to complete...")
        time.sleep(30)

        self.wait_for_input()

        # Step 6: Cleanup
        print("\n📋 Step 6: Cleanup")
        print("🧹 Cleaning up monitoring environment...")

        # Stop all containers
        containers = ["cpu-hog", "memory-user", "idle-container", "healthy-nginx", "stress-test"]
        for container in containers:
            self.run_command(f"docker stop {container}", capture_output=True)
            self.run_command(f"docker rm {container}", capture_output=True)

        # Stop monitoring stack
        self.run_command("docker-compose -f monitoring-compose.yml down")

        # Remove images
        self.run_command("docker rmi nginx-healthy", capture_output=True)

        print("\n🎉 Monitoring experiment complete!")
        print("📚 Key concepts learned:")
        print("   • docker stats for real-time monitoring")
        print("   • cAdvisor for detailed metrics collection")
        print("   • Health checks with HEALTHCHECK instruction")
        print("   • Resource monitoring and alerting")
        print("   • Performance testing and stress analysis")
        print("   • Docker system monitoring")

    def experiment_security(self):
        """Experiment 8: Container Security."""
        print("🔒 Experiment: Container Security")
        print("=" * 50)
        print("🎯 Learning Goals:")
        print("   • Understand container security risks")
        print("   • Implement security best practices")
        print("   • Use non-root users in containers")
        print("   • Scan for vulnerabilities")
        print()

        # Step 1: Security assessment
        print("📋 Step 1: Security Assessment")

        # Create insecure container example
        insecure_dockerfile = """FROM ubuntu:20.04

# BAD: Running as root user
USER root

# BAD: Installing unnecessary packages
RUN apt-get update && apt-get install -y \\
    curl \\
    vim \\
    sudo \\
    ssh \\
    && rm -rf /var/lib/apt/lists/*

# BAD: Exposing SSH
EXPOSE 22

# BAD: Weak permissions
RUN chmod 777 /tmp

# Application
COPY app.sh /app.sh
RUN chmod +x /app.sh

CMD ["/app.sh"]
"""

        app_script = """#!/bin/bash
echo "🚨 This is an INSECURE container!"
echo "Current user: $(whoami)"
echo "User ID: $(id)"
echo "Writable directories:"
find / -type d -writable 2>/dev/null | head -10
echo "Listening on port 22..."
sleep 3600
"""

        self.create_file("Dockerfile.insecure", insecure_dockerfile, "INSECURE container (for demonstration)")
        self.create_file("app.sh", app_script, "Application script")

        # Build insecure image
        print("\n🔨 Building insecure container (for demonstration)...")
        self.run_command("docker build -f Dockerfile.insecure -t insecure-app .")

        # Run and analyze
        self.run_command("docker run --rm insecure-app")

        print("\n🚨 Security Issues Identified:")
        print("   • Running as root user")
        print("   • Unnecessary packages installed")
        print("   • SSH service exposed")
        print("   • Overly permissive file permissions")

        self.wait_for_input()

        # Step 2: Secure container implementation
        print("\n📋 Step 2: Secure Container Implementation")

        secure_dockerfile = """# Use minimal base image
FROM python:3.11-alpine

# Create non-root user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

# Install only necessary packages
RUN apk add --no-cache --virtual .build-deps gcc musl-dev \\
    && apk del .build-deps

# Set working directory
WORKDIR /app

# Copy and install requirements as root, then switch user
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files with correct ownership
COPY --chown=appuser:appgroup secure_app.py .

# Switch to non-root user
USER appuser

# Use specific port (not privileged)
EXPOSE 8080

# Remove unnecessary setuid binaries
RUN find /usr/bin /usr/sbin -perm -4000 -exec rm {} + 2>/dev/null || true

# Read-only filesystem (except /tmp)
VOLUME ["/tmp"]

# Health check
HEALTHCHECK --interval=30s --timeout=3s \\
    CMD python -c "import requests; requests.get('http://localhost:8080/health')" || exit 1

CMD ["python", "secure_app.py"]
"""

        secure_app = """#!/usr/bin/env python3
from flask import Flask, jsonify
import os
import pwd

app = Flask(__name__)

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

@app.route('/')
def info():
    try:
        user_info = pwd.getpwuid(os.getuid())
        return jsonify({
            "message": "🔒 Secure container running!",
            "user": user_info.pw_name,
            "uid": os.getuid(),
            "gid": os.getgid(),
            "writable_dirs": [
                d for d in ["/tmp", "/app"]
                if os.access(d, os.W_OK)
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
"""

        requirements_secure = """Flask==2.3.3
requests==2.31.0
"""

        self.create_file("Dockerfile.secure", secure_dockerfile, "SECURE container implementation")
        self.create_file("secure_app.py", secure_app, "Secure application")
        self.create_file("requirements.txt", requirements_secure, "Minimal dependencies")

        # Build secure image
        print("\n🔨 Building secure container...")
        self.run_command("docker build -f Dockerfile.secure -t secure-app .")

        # Run secure container
        self.run_command("docker run -d --name secure-container -p 8080:8080 secure-app")

        time.sleep(5)

        # Test secure container
        print("\n✅ Testing secure container...")
        self.run_command("curl -s http://localhost:8080 | python3 -m json.tool")

        self.wait_for_input()

        # Step 3: Security scanning
        print("\n📋 Step 3: Vulnerability Scanning")

        # Check if trivy is available
        result, _, _ = self.run_command("trivy --version", capture_output=True, show_command=False)

        if result == 0:
            print("🔍 Scanning for vulnerabilities with Trivy...")
            self.run_command("trivy image --severity HIGH,CRITICAL secure-app")
        else:
            print("⚠️ Trivy not installed. Here's how to scan manually:")
            print("   • Install Trivy: https://github.com/aquasecurity/trivy")
            print("   • Run: trivy image secure-app")
            print("   • Also try: docker scan secure-app (if available)")

        # Manual security checks
        print("\n🔍 Manual security inspection...")

        # Check user
        self.run_command("docker run --rm secure-app whoami")

        # Check file permissions
        self.run_command("docker run --rm secure-app ls -la /app")

        # Check running processes
        self.run_command("docker exec secure-container ps aux")

        self.wait_for_input()

        # Step 4: Runtime security
        print("\n📋 Step 4: Runtime Security Configuration")

        # Create security-hardened run configuration
        print("🛡️ Running container with security hardening...")

        self.run_command("docker stop secure-container")
        self.run_command("docker rm secure-container")

        # Run with security options
        security_run_cmd = """docker run -d \\
    --name hardened-container \\
    --read-only \\
    --tmpfs /tmp \\
    --tmpfs /run \\
    --cap-drop ALL \\
    --cap-add NET_BIND_SERVICE \\
    --security-opt no-new-privileges \\
    --user 1000:1000 \\
    -p 8080:8080 \\
    secure-app"""

        print(f"🔧 Running: {security_run_cmd}")
        self.run_command(security_run_cmd.replace('\\\n    ', ' ').replace('    ', ''))

        time.sleep(5)

        print("\n💡 Security options explained:")
        print("   • --read-only: Root filesystem is read-only")
        print("   • --tmpfs: Writable temporary filesystems")
        print("   • --cap-drop ALL: Remove all Linux capabilities")
        print("   • --cap-add NET_BIND_SERVICE: Allow binding to port")
        print("   • --security-opt no-new-privileges: Prevent privilege escalation")
        print("   • --user: Run as specific user ID")

        # Test hardened container
        print("\n✅ Testing hardened container...")
        self.run_command("curl -s http://localhost:8080 | python3 -m json.tool")

        self.wait_for_input()

        # Step 5: Secret management
        print("\n📋 Step 5: Secret Management")

        # Create secret management example
        print("🔐 Demonstrating secure secret handling...")

        # Create secret file
        secret_content = "supersecretpassword123"
        secret_file = self.temp_dir / "secret.txt"
        with open(secret_file, 'w') as f:
            f.write(secret_content)

        # Mount secret as read-only
        self.run_command(f"docker run --rm -v {secret_file}:/run/secrets/password:ro alpine cat /run/secrets/password")

        print("\n💡 Secret management best practices:")
        print("   • Mount secrets as read-only volumes")
        print("   • Use dedicated secret directories (/run/secrets)")
        print("   • Never include secrets in images")
        print("   • Use Docker Swarm secrets or external secret stores")

        # Demonstrate bad practice (secrets in environment)
        print("\n🚨 BAD PRACTICE - secrets in environment:")
        self.run_command("docker run --rm -e SECRET_PASSWORD=badpractice alpine env | grep SECRET")

        print("❌ Environment variables are visible to all processes!")

        self.wait_for_input()

        # Step 6: Security monitoring
        print("\n📋 Step 6: Security Monitoring")

        # Create security monitoring script
        security_monitor = """#!/bin/bash
echo "🔒 Container Security Monitoring Report"
echo "======================================"

echo -e "\\n📊 Running Containers:"
docker ps --format "table {{.Names}}\\t{{.Image}}\\t{{.Status}}"

echo -e "\\n🔍 Container Running as Root:"
for container in $(docker ps -q); do
    name=$(docker inspect --format '{{.Name}}' $container | sed 's/^\\///')
    user=$(docker exec $container whoami 2>/dev/null || echo "unknown")
    if [ "$user" = "root" ]; then
        echo "⚠️  $name: running as ROOT user"
    else
        echo "✅ $name: running as $user"
    fi
done

echo -e "\\n🔒 Security Options Check:"
for container in $(docker ps -q); do
    name=$(docker inspect --format '{{.Name}}' $container | sed 's/^\\///')
    readonly=$(docker inspect --format '{{.HostConfig.ReadonlyRootfs}}' $container)
    privileged=$(docker inspect --format '{{.HostConfig.Privileged}}' $container)

    echo "Container: $name"
    echo "  Read-only: $readonly"
    echo "  Privileged: $privileged"
done

echo -e "\\n✅ Security monitoring complete!"
"""

        self.create_file("security_monitor.sh", security_monitor, "Security monitoring script")
        self.run_command("chmod +x security_monitor.sh")
        self.run_command("./security_monitor.sh")

        self.wait_for_input()

        # Step 7: Cleanup
        print("\n📋 Step 7: Cleanup")
        print("🧹 Cleaning up security experiment...")

        self.run_command("docker stop hardened-container", capture_output=True)
        self.run_command("docker rm hardened-container", capture_output=True)
        self.run_command("docker rmi insecure-app secure-app", capture_output=True)

        print("\n🎉 Security experiment complete!")
        print("📚 Key concepts learned:")
        print("   • Non-root users in containers")
        print("   • Minimal base images and packages")
        print("   • Runtime security hardening")
        print("   • Vulnerability scanning")
        print("   • Secret management best practices")
        print("   • Security monitoring and assessment")
        print("   • Read-only filesystems and capabilities")

    def list_experiments(self):
        """List all available experiments."""
        print("🧪 Available Docker Learning Experiments")
        print("=" * 50)

        for key, exp in self.experiments.items():
            print(f"\n🎯 {key}: {exp['name']}")
            print(f"   📝 {exp['description']}")
            print(f"   🎓 Difficulty: {exp['difficulty']}")
            print(f"   ⏱️ Duration: {exp['duration']}")

    def run_experiment(self, experiment_name: str):
        """Run a specific experiment."""
        if experiment_name not in self.experiments:
            print(f"❌ Experiment '{experiment_name}' not found!")
            self.list_experiments()
            return

        exp = self.experiments[experiment_name]

        print(f"\n🚀 Starting Experiment: {exp['name']}")
        print(f"📝 {exp['description']}")
        print(f"🎓 Difficulty: {exp['difficulty']} | ⏱️ Duration: {exp['duration']}")

        self.wait_for_input("Press Enter to begin...")

        start_time = time.time()

        try:
            # Run the experiment function
            exp['function']()

            duration = time.time() - start_time
            print(f"\n✅ Experiment completed successfully!")
            print(f"⏱️ Time taken: {duration:.1f} seconds")

        except KeyboardInterrupt:
            print(f"\n⏹️ Experiment interrupted by user")
        except Exception as e:
            print(f"\n❌ Experiment failed: {e}")

        # Log experiment completion
        self.session_log.append({
            "timestamp": datetime.now().isoformat(),
            "experiment": experiment_name,
            "status": "completed",
            "duration": duration if 'duration' in locals() else 0,
            "type": "experiment"
        })

    def interactive_mode(self):
        """Run playground in interactive mode."""
        print("\n🎮 Interactive Mode")
        print("Type 'help' for commands, 'quit' to exit")

        while True:
            try:
                command = input("\n🐳 playground> ").strip()

                if command == "quit" or command == "exit":
                    break
                elif command == "help":
                    print("\nAvailable commands:")
                    print("  list - Show all experiments")
                    print("  run <experiment> - Run specific experiment")
                    print("  log - Show session log")
                    print("  clean - Clean up Docker resources")
                    print("  quit - Exit playground")
                elif command == "list":
                    self.list_experiments()
                elif command.startswith("run "):
                    exp_name = command[4:].strip()
                    self.run_experiment(exp_name)
                elif command == "log":
                    self.show_session_log()
                elif command == "clean":
                    self.cleanup_docker()
                elif command == "":
                    continue
                else:
                    print(f"Unknown command: {command}")
                    print("Type 'help' for available commands")

            except KeyboardInterrupt:
                print("\nUse 'quit' to exit")
            except EOFError:
                break

    def show_session_log(self):
        """Show session activity log."""
        print("\n📋 Session Activity Log")
        print("=" * 30)

        for entry in self.session_log[-10:]:  # Show last 10 entries
            timestamp = entry['timestamp'][:19]  # Remove microseconds
            if entry['type'] == 'command':
                print(f"{timestamp} 🔧 {entry['command']}")
            elif entry['type'] == 'experiment':
                print(f"{timestamp} 🧪 {entry['experiment']} ({entry['status']})")

    def cleanup_docker(self):
        """Clean up Docker resources."""
        print("🧹 Cleaning up Docker resources...")

        # Stop all containers
        self.run_command("docker stop $(docker ps -q)", capture_output=True)

        # Remove stopped containers
        self.run_command("docker container prune -f", capture_output=True)

        # Remove unused images
        self.run_command("docker image prune -f", capture_output=True)

        # Remove unused volumes
        self.run_command("docker volume prune -f", capture_output=True)

        # Remove unused networks
        self.run_command("docker network prune -f", capture_output=True)

        print("✅ Docker cleanup complete!")

    def __del__(self):
        """Cleanup when playground is destroyed."""
        if hasattr(self, 'temp_dir') and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
            print(f"🧹 Cleaned up temporary directory: {self.temp_dir}")


def main():
    """Main function to run the Docker playground."""
    parser = argparse.ArgumentParser(description="🐳 Docker Learning Playground")
    parser.add_argument(
        "experiment",
        nargs="?",
        help="Experiment to run (use 'list' to see all)"
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Run in interactive mode"
    )

    args = parser.parse_args()

    # Create playground instance
    playground = DockerPlayground()

    try:
        if args.interactive:
            playground.interactive_mode()
        elif args.experiment:
            if args.experiment == "list":
                playground.list_experiments()
            else:
                playground.run_experiment(args.experiment)
        else:
            # Default behavior - show menu
            playground.list_experiments()
            print("\nUsage:")
            print("  python docker_playground.py <experiment_name>")
            print("  python docker_playground.py --interactive")
            print("  python docker_playground.py list")

    except KeyboardInterrupt:
        print("\n\n👋 Thanks for using Docker Learning Playground!")
    finally:
        playground.cleanup_docker()


if __name__ == "__main__":
    main()