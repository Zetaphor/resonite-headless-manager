from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import asyncio
from docker_manager import DockerManager
import json
import threading
from functools import partial

app = FastAPI()

# Serve static files (if you have any CSS/JS files)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Store active WebSocket connections
active_connections = []

# Initialize DockerManager
docker_manager = DockerManager("resonite-headless")  # Replace with your container name

@app.get("/")
async def get():
    with open("templates/index.html") as f:
        return HTMLResponse(f.read())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)

    try:
        # Start monitoring Docker output in a separate task
        monitor_task = asyncio.create_task(monitor_docker_output(websocket))

        # Handle incoming messages
        while True:
            message = await websocket.receive_text()
            try:
                data = json.loads(message)
                if data["type"] == "command":
                    # Execute command and send response
                    output = docker_manager.send_command(data["command"])
                    await websocket.send_json({
                        "type": "command_response",
                        "output": output
                    })
                elif data["type"] == "get_status":
                    # Get container status
                    status = docker_manager.get_container_status()
                    await websocket.send_json({
                        "type": "status_update",
                        "status": status
                    })
                elif data["type"] == "get_worlds":
                    worlds_output = docker_manager.send_command("worlds")

                    # Remove the command and the command prompt
                    worlds_output = worlds_output.split('\n')[1:-1]
                    print(len(worlds_output))

                    worlds = []
                    for world in worlds_output:
                        # Split by tabs to separate the main sections
                        parts = world.split('\t')

                        # Extract name and index from the first part
                        name_part = parts[0]
                        # Find the position where "Users:" starts
                        users_index = name_part.find("Users:")
                        # Extract just the name portion (removing the index and trailing spaces)
                        name = name_part[name_part.find(']') + 2:users_index].strip()

                        # Extract users count from the first part
                        users = int(name_part[users_index:].split(': ')[1])
                        # Extract remaining values
                        present = int(parts[1].split(': ')[1])
                        accessLevel = parts[2].split(': ')[1]
                        maxUsers = int(parts[3].split(': ')[1])

                        worlds.append({
                            "name": name,
                            "users": users,
                            "present": present,
                            "accessLevel": accessLevel,
                            "maxUsers": maxUsers,
                        })

                    print(worlds)

                    await websocket.send_json({
                        "type": "worlds_update",
                        "output": worlds
                    })
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid message format"
                })

    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        active_connections.remove(websocket)
        monitor_task.cancel()

async def monitor_docker_output(websocket: WebSocket):
    """Monitor Docker output and send to WebSocket"""
    loop = asyncio.get_running_loop()

    async def async_callback(output):
        await send_output(websocket, output)

    def sync_callback(output):
        asyncio.run_coroutine_threadsafe(async_callback(output), loop)

    # Run the monitoring in a separate thread
    thread = threading.Thread(
        target=docker_manager.monitor_output,
        args=(sync_callback,),
        daemon=True
    )
    thread.start()

    try:
        while True:
            await asyncio.sleep(1)  # Keep the monitoring alive
    except asyncio.CancelledError:
        # Cleanup when the task is cancelled
        pass

async def send_output(websocket: WebSocket, output):
    """Send output to WebSocket"""
    try:
        await websocket.send_json({
            "type": "container_output",
            "output": output
        })
    except Exception as e:
        print(f"Error sending output: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)