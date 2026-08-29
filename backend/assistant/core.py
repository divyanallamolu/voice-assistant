def get_response(message: str) -> str:
    message = message.lower().strip()

    if message == "hello":
        return "Hello! How can I help you?"

    if "your name" in message:
        return "I am your voice assistant."

    if "how are you" in message:
        return "I'm doing great! Thanks for asking."

    return f"You said: {message}"