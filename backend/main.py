from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def home():
    return {"message": "Voice Assistant Backend is running!"}