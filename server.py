from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import asyncio
from docker_manager import DockerManager
import json
import threading
from functools import partial
import time

app = FastAPI()

# Serve static files (if you have any CSS/JS files)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Store active WebSocket connections
active_connections = []

# Initialize DockerManager
docker_manager = DockerManager("resonite-headless")  # Replace with your container name

def format_uptime(uptime_str):
    """Convert .NET TimeSpan format to human readable format"""
    try:
        # Split into days, hours, minutes, seconds
        parts = uptime_str.split('.')
        if len(parts) != 2:
            return uptime_str

        days = 0
        time_parts = parts[0].split(':')
        if len(time_parts) != 3:
            return uptime_str

        hours, minutes, seconds = map(int, time_parts)

        # Handle days if present
        if hours >= 24:
            days = hours // 24
            hours = hours % 24

        # Build readable string
        components = []
        if days > 0:
            components.append(f"{days} {'day' if days == 1 else 'days'}")
        if hours > 0:
            components.append(f"{hours} {'hour' if hours == 1 else 'hours'}")
        if not days and minutes > 0:  # Only show minutes if less than a day
            components.append(f"{minutes} {'minute' if minutes == 1 else 'minutes'}")

        return ' '.join(components) if components else "just started"
    except:
        return uptime_str

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
                    for i, world in enumerate(worlds_output):
                        # First focus on this world
                        docker_manager.send_command(f"focus {i}")
                        # Add delay to prevent overwhelming the container
                        time.sleep(1)

                        # Get detailed status
                        status_output = docker_manager.send_command("status")
                        status_lines = status_output.split('\n')[1:-1]  # Remove command and prompt

                        # Parse status output
                        status_data = {}
                        for line in status_lines:
                            if ': ' in line:
                                key, value = line.split(': ', 1)
                                status_data[key] = value

                        # Split by tabs to separate the main sections (from original worlds command)
                        parts = world.split('\t')

                        # Extract name and index from the first part
                        name_part = parts[0]
                        users_index = name_part.find("Users:")
                        name = name_part[name_part.find(']') + 2:users_index].strip()

                        # Create world data combining both outputs
                        world_data = {
                            "name": name,
                            "sessionId": status_data.get("SessionID", ""),
                            "users": int(status_data.get("Current Users", 0)),
                            "present": int(status_data.get("Present Users", 0)),
                            "maxUsers": int(status_data.get("Max Users", 0)),
                            "uptime": format_uptime(status_data.get("Uptime", "")),
                            "accessLevel": status_data.get("Access Level", ""),
                            "hidden": status_data.get("Hidden from listing", "False") == "True",
                            "mobileFriendly": status_data.get("Mobile Friendly", "False") == "True",
                            "description": status_data.get("Description", ""),
                            "tags": status_data.get("Tags", ""),
                            "userList": status_data.get("Users", "").strip().split()
                        }

                        worlds.append(world_data)

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