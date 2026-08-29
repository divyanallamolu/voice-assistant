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

            try:
                response = get_response(message)

                print(f"Assistant: {response}")

                await websocket.send_text(response)

            except Exception as e:
                print("GEMINI ERROR:", e)
                await websocket.send_text(
                    "Sorry, something went wrong while generating the answer."
                )

    except WebSocketDisconnect:
        print("Client disconnected!")