from fastapi import FastAPI, WebSocket, WebSocketDisconnect

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

            print(f"Received: {message}")

            await websocket.send_text(
                f"Backend received: {message}"
            )

    except WebSocketDisconnect:
        print("Client disconnected!")