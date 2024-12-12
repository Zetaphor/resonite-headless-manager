import docker
import select
import time
import re
from collections import deque
from threading import Lock

class DockerManager:
    def __init__(self, container_name):
        self.client = docker.from_env()
        self.container_name = container_name
        self.output_buffer = deque(maxlen=1000)  # Rolling buffer of last 1000 lines
        self.buffer_lock = Lock()  # Thread-safe access to buffer
        # Regex pattern for ANSI escape sequences
        self.ansi_escape = re.compile(r'(\x9B|\x1B\[)[0-?]*[ -/]*[@-~]|\x1B[()][AB012]')
        self._monitor_running = False

    def clean_output(self, text):
        """Clean and format output text by removing ANSI sequences and handling line breaks"""
        # Remove all ANSI escape sequences
        clean_text = self.ansi_escape.sub('', text)

        # Split on both \r\n and \n, and filter out empty lines
        lines = [line.strip() for line in clean_text.replace('\r\n', '\n').split('\n')]
        return [line for line in lines if line]  # Return only non-empty lines


    def add_to_buffer(self, text):
        with self.buffer_lock:
            clean_lines = self.clean_output(text)
            for line in clean_lines:
                self.output_buffer.append(line)

    def get_recent_lines(self, count=50):
        with self.buffer_lock:
            return list(self.output_buffer)[-count:]

    def send_command(self, command, timeout=1):
        """Send a command to the container and return the output"""
        try:
            container = self.client.containers.get(self.container_name)

            # Get raw connection to container
            socket = container.attach_socket(params={
                'stdin': True,
                'stdout': True,
                'stderr': True,
                'stream': True,
                'logs': True
            })

            # Send the command with both carriage return and newline
            cmd_bytes = f"{command}\r\n".encode('utf-8')
            socket._sock.send(cmd_bytes)

            # Read the response with timeout
            output = []
            start_time = time.time()
            no_data_count = 0  # Counter for consecutive no-data readings

            while True:
                ready = select.select([socket._sock], [], [], 0.1)
                if ready[0]:
                    chunk = socket._sock.recv(4096).decode('utf-8')
                    if chunk:
                        output.append(chunk)
                        no_data_count = 0  # Reset counter when we get data
                        continue

                no_data_count += 1
                # Break if we've had no data for 3 consecutive reads or exceeded timeout
                if no_data_count >= 3 or (time.time() - start_time > timeout):
                    break

            socket.close()
            result = ''.join(output).strip()
            # Use clean_output instead of direct ANSI escape removal
            clean_lines = self.clean_output(result)
            return '\n'.join(clean_lines)

        except docker.errors.NotFound:
            return f"Container {self.container_name} not found"
        except Exception as e:
            return f"Error: {str(e)}"

    def monitor_output(self, callback):
        """Monitor container output continuously"""
        self._monitor_running = True
        buffer = ""
        try:
            container = self.client.containers.get(self.container_name)
            socket = container.attach_socket(params={
                'stdin': False,
                'stdout': True,
                'stderr': True,
                'stream': True,
                'logs': True
            })

            # Send initial carriage returns to get prompt
            cmd_socket = container.attach_socket(params={
                'stdin': True,
                'stdout': True,
                'stderr': True,
                'stream': True
            })
            cmd_socket._sock.send(b'\r\n')
            cmd_socket.close()

            while self._monitor_running:
                ready = select.select([socket._sock], [], [], 0.1)
                if ready[0]:
                    try:
                        chunk = socket._sock.recv(4096).decode('utf-8')
                        if chunk:
                            # Append chunk to buffer
                            buffer += chunk

                            # Process complete lines
                            while '\n' in buffer:
                                line, buffer = buffer.split('\n', 1)
                                line = line.strip()
                                if line:
                                    # Use clean_output for single line
                                    clean_lines = self.clean_output(line)
                                    for clean_line in clean_lines:
                                        self.add_to_buffer(clean_line)
                                        callback(clean_line + '\n')

                            # If buffer gets too large, clear it
                            if len(buffer) > 8192:
                                buffer = buffer[-4096:]

                    except Exception as e:
                        print(f"Error reading from socket: {e}")
                        break

        except docker.errors.NotFound:
            print(f"Container {self.container_name} not found")
        except Exception as e:
            print(f"Error: {str(e)}")
        finally:
            self._monitor_running = False
            try:
                socket.close()
            except:
                pass

    def get_container_status(self):
        """Get container status information"""
        try:
            container = self.client.containers.get(self.container_name)
            return {
                'status': container.status,
                'name': container.name,
                'id': container.id
            }
        except Exception as e:
            return {'error': str(e)}

    def parse_status_output(self, output):
        """Parse the status command output into a structured format"""
        status_data = {}
        lines = output.strip().split('\n')
        for line in lines:
            clean_line = re.sub(r'<color=#[0-9a-fA-F]{6}>', '', line)
            clean_line = clean_line.replace('<color=#ffffff>', '')

            if ':' in clean_line:
                key, value = clean_line.split(':', 1)
                status_data[key.strip()] = value.strip()

        return status_data