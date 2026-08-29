from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from backend.assistant.core import get_response

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Voice Assistant Backend is running!"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    print("Client connected!")

    try:
        while True:
            message = await websocket.receive_text()

            print(f"User: {message}")

            response = get_response(message)

            print(f"Assistant: {response}")

            await websocket.send_text(response)

    except WebSocketDisconnect:
        print("Client disconnected!")