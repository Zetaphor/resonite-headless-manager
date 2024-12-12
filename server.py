from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import asyncio
from docker_manager import DockerManager
import json

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
    def callback(output):
        asyncio.create_task(send_output(websocket, output))

    # Run the monitoring in a thread pool executor
    await asyncio.get_event_loop().run_in_executor(
        None,
        docker_manager.monitor_output,
        callback
    )

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