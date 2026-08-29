def get_response(message: str) -> str:
    message = message.lower().strip()

    if message == "hello" or message == "hi":
        return "Hello! How can I help you?"

    elif "your name" in message:
        return "I am your voice assistant."

    elif "how are you" in message:
        return "I'm doing great! Thanks for asking."

    elif "what can you do" in message:
        return "I can answer simple questions and help you with basic tasks."

    elif "good morning" in message:
        return "Good morning! Have a great day."

    elif "thank you" in message or "thanks" in message:
        return "You're welcome!"

    elif "bye" in message:
        return "Goodbye! Have a nice day."

    else:
        return f"You said: {message}"