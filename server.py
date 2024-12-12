from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import asyncio
from docker_manager import DockerManager
import json
import threading
from functools import partial
import time
from dotenv import load_dotenv
import os
from typing import Dict, Any

# Load environment variables
load_dotenv()

app = FastAPI()

# Serve static files (if you have any CSS/JS files)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Store active WebSocket connections
active_connections = []

# Initialize DockerManager with container name from .env
docker_manager = DockerManager(os.getenv('CONTAINER_NAME', 'resonite-headless'))  # Fallback to 'resonite-headless' if not set

# Add config file handling
def load_config() -> Dict[Any, Any]:
    """Load the headless config file"""
    config_path = os.getenv('CONFIG_PATH')
    if not config_path:
        raise ValueError("CONFIG_PATH not set in environment variables")

    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON in config file")
    except FileNotFoundError:
        raise ValueError(f"Config file not found at {config_path}")

def save_config(config_data: Dict[Any, Any]) -> None:
    """Save the headless config file"""
    config_path = os.getenv('CONFIG_PATH')
    if not config_path:
        raise ValueError("CONFIG_PATH not set in environment variables")

    # Validate JSON before saving
    try:
        # Test if the data can be serialized
        json.dumps(config_data)
    except (TypeError, json.JSONDecodeError):
        raise ValueError("Invalid JSON data")

    with open(config_path, 'w') as f:
        json.dump(config_data, f, indent=2)

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

                    worlds = []
                    for i, world in enumerate(worlds_output):
                        # First focus on this world
                        docker_manager.send_command(f"focus {i}")
                        # Add delay to prevent overwhelming the container
                        time.sleep(1)

                        # Get detailed status
                        status_output = docker_manager.send_command("status")
                        status_lines = status_output.split('\n')[1:-1]  # Remove command and prompt

                        # Get the focused world name
                        focused_world_name = status_lines[-1][:-1]

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
                            "tags": status_data.get("Tags", "")
                        }

                        # Send the users command to the focused world
                        users_output = docker_manager.send_command(f"users")
                        # Remove command and prompt lines
                        users_lines = users_output.split('\n')[1:-1]

                        # Parse users
                        users_data = []
                        for user_line in users_lines:
                            if user_line.strip():  # Skip empty lines
                                user_info = {}
                                # Split by spaces but preserve quoted strings
                                parts = user_line.split()

                                # Get username (everything before "ID:")
                                id_index = user_line.find("ID:")
                                if id_index != -1:
                                    user_info["username"] = user_line[:id_index].strip()

                                # Parse key-value pairs
                                for i in range(len(parts)):
                                    if parts[i].endswith(":") and i + 1 < len(parts):
                                        key = parts[i][:-1].lower()  # Remove colon and convert to lowercase
                                        value = parts[i + 1]
                                        if key == "present":
                                            value = value.lower() == "true"
                                        elif key == "ping":
                                            value = int(value)
                                        elif key == "fps":
                                            value = float(value)
                                        elif key == "silenced":
                                            value = value.lower() == "true"
                                        user_info[key] = value

                                users_data.append(user_info)

                        # Add users data to world_data
                        world_data["users_list"] = users_data

                        worlds.append(world_data)

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

async def is_websocket_connected(websocket: WebSocket) -> bool:
    """Check if the websocket is still connected"""
    try:
        # Try sending a ping frame
        await websocket.send_bytes(b'')
        return True
    except:
        return False

async def monitor_docker_output(websocket: WebSocket):
    """Monitor Docker output and send to WebSocket"""
    loop = asyncio.get_running_loop()

    async def async_callback(output):
        if await is_websocket_connected(websocket):
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
        while await is_websocket_connected(websocket):
            await asyncio.sleep(1)  # Keep the monitoring alive
    except asyncio.CancelledError:
        # Cleanup when the task is cancelled
        pass

async def send_output(websocket: WebSocket, output):
    """Send output to WebSocket"""
    try:
        if await is_websocket_connected(websocket):
            # Ensure the output is properly encoded
            if not isinstance(output, str):
                output = str(output)

            await websocket.send_json({
                "type": "container_output",
                "output": output
            })
    except Exception as e:
        print(f"Error sending output: {e}")

@app.get("/config")
async def get_config():
    """Get the current headless config"""
    try:
        config = load_config()
        return JSONResponse(content=config)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/config")
async def update_config(config_data: Dict[Any, Any]):
    """Update the headless config"""
    try:
        save_config(config_data)
        return JSONResponse(content={"message": "Config updated successfully"})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)