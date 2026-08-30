# JARVIS Voice Assistant

A browser-based voice assistant built with FastAPI. You speak into the microphone, the backend transcribes your speech, Groq generates a response (with tool calling when needed), and ElevenLabs reads the answer back.

## Features

- Real-time speech-to-text (Deepgram Nova-3)
- Voice responses (ElevenLabs)
- Groq LLM with function calling
- Weather lookup for any city
- Reminders stored in SQLite with background notifications
- WebSocket session handling
- Latency timing for each voice turn

## Tech stack

- **Backend:** Python, FastAPI, WebSockets
- **Speech:** Deepgram (STT), ElevenLabs (TTS)
- **LLM:** Groq (`openai/gpt-oss-20b`)
- **Database:** SQLite
- **Frontend:** HTML, CSS, JavaScript

## How it works

```
Browser mic (16 kHz PCM)
  → WebSocket
  → Deepgram (transcript)
  → Groq (reply or tool call)
  → Weather / reminder tools (if needed)
  → ElevenLabs (MP3 audio)
  → Browser playback
```

## Project structure

```
voice-assistant/
├── backend/
│   ├── main.py              # FastAPI app + WebSocket pipeline
│   ├── database.py          # SQLite reminders
│   ├── scheduler.py         # Due reminder notifications
│   ├── data/                # Local DB (created at runtime)
│   ├── assistant/
│   │   ├── core.py          # Groq + tool loop
│   │   ├── elevenlabs_tts.py
│   │   ├── latency.py
│   │   └── transcript_normalize.py
│   └── tools/
│       ├── executor.py
│       ├── weather.py
│       └── reminders.py
├── frontend/
│   ├── index.html           # Main UI
│   ├── app.js
│   └── style.css
├── requirements.txt
└── .env                     # API keys (not committed)
```

## Prerequisites

- Python 3.10 or newer
- API keys for Deepgram, Groq, ElevenLabs, and WeatherAPI.com
- A modern browser with microphone access (Chrome or Edge recommended)

## Setup

### 1. Clone and create a virtual environment

```bash
cd voice-assistant
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Environment variables

Create a `.env` file in the project root:

```env
DEEPGRAM_API_KEY=your_deepgram_key
GROQ_API_KEY=your_groq_key
GROQ_MODEL=openai/gpt-oss-20b
ELEVENLABS_API_KEY=your_elevenlabs_key
WEATHER_API_KEY=your_weatherapi_key
```

Optional:

```env
TIMEZONE=Asia/Kolkata
JARVIS_DB_PATH=backend/data/jarvis.db
```

Store all secrets in `.env` only. Do not commit that file or share keys publicly.

### 4. Run the backend

From the project root (`voice-assistant/`):

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

The SQLite database is created automatically on first startup.

### 5. Open the frontend

Serve the `frontend/` folder with a local static server. Opening `index.html` directly with `file://` often blocks microphone access.

```bash
cd frontend
python -m http.server 5500
```

Open `http://127.0.0.1:5500` in your browser. Allow microphone and notification permissions when prompted.

The frontend connects to `ws://127.0.0.1:8000/ws`.

## Using the app

1. Start the backend (`uvicorn` on port 8000).
2. Open the frontend in your browser.
3. Wait until the status shows **CONNECTED**.
4. Click the microphone button, speak, then click again to stop.
5. JARVIS transcribes your speech, responds, and plays audio back.
6. You can also type a message in the text box and press Send.

Reminder notifications appear in the UI and as browser notifications (if allowed).

## Usage examples

Try saying or typing:

- "Hello Jarvis"
- "What is the weather in Vizag?"
- "Remind me in one minute to call mom"
- "Show my reminders"
- "Cancel my reminder about calling mom"

## Troubleshooting

| Problem | What to check |
|--------|----------------|
| Mic not working | Use `http://localhost`, not `file://`. Grant mic permission in the browser. |
| WebSocket disconnected | Backend running on port 8000? Check the terminal for errors. |
| No voice reply | `ELEVENLABS_API_KEY` set in `.env`? Check backend logs. |
| Weather tool fails | Use a [WeatherAPI.com](https://www.weatherapi.com/) key as `WEATHER_API_KEY`. |
| Groq errors | Confirm `GROQ_API_KEY` and `GROQ_MODEL` in `.env`. |

Latency summaries print in the backend terminal after each voice response.

## Notes

- Reminders use the `Asia/Kolkata` timezone by default.
- Weather data comes from WeatherAPI.com.
