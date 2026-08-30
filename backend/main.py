import asyncio
import base64
import json
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from deepgram import AsyncDeepgramClient
from deepgram.core.events import EventType

from backend.assistant.core import get_response_async
from backend.assistant.elevenlabs_tts import iter_speech_chunks
from backend.assistant.latency import LatencyTracker
from backend.assistant.transcript_normalize import normalize_transcript
from backend.database import init_db
from backend.scheduler import (
    register_connection,
    start_reminder_scheduler,
    unregister_connection,
)


@asynccontextmanager
async def lifespan(app):

    init_db()

    scheduler_task = start_reminder_scheduler()

    yield

    scheduler_task.cancel()

    try:

        await scheduler_task

    except asyncio.CancelledError:

        pass


app = FastAPI(lifespan=lifespan)


# ============================================================
# HOME
# ============================================================

@app.get("/")
async def home():
    return {
        "message": "Voice Assistant Backend Running"
    }


# ============================================================
# WEBSOCKET
# ============================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):

    await websocket.accept()

    print("🟢 Browser WebSocket connected")

    session_state = {
        "id": str(uuid.uuid4()),
    }

    latency_trackers: dict[str, LatencyTracker] = {}
    active_request_id: str | None = None
    finalizing_request_id: str | None = None
    utterance_pcm_open = False

    def begin_utterance() -> str:

        nonlocal active_request_id, utterance_pcm_open

        request_id = uuid.uuid4().hex

        tracker = LatencyTracker(request_id)
        tracker.start()

        latency_trackers[request_id] = tracker
        active_request_id = request_id
        utterance_pcm_open = True

        return request_id

    def get_active_tracker() -> LatencyTracker | None:

        if not active_request_id:
            return None

        return latency_trackers.get(
            active_request_id
        )

    def complete_latency(
        request_id: str,
    ) -> None:

        latency_trackers.pop(
            request_id,
            None,
        )

        nonlocal active_request_id

        if active_request_id == request_id:
            active_request_id = None

    DEEPGRAM_KEYTERMS = [
        "Vizag",
        "Visakhapatnam",
        "Jarvis",
        "Vizianagaram",
    ]

    register_connection(
        session_state["id"],
        websocket,
    )

    await websocket.send_text(
        json.dumps({
            "type": "session",
            "session_id": session_state["id"],
        })
    )

    async def emit_event(event):

        await websocket.send_text(
            json.dumps(event)
        )

    async def send_assistant_response(
        response,
        request_id: str | None,
    ):

        await websocket.send_text(
            json.dumps({
                "type": "assistant",
                "text": response,
            })
        )

        tracker = (
            latency_trackers.get(request_id)
            if request_id
            else None
        )

        try:

            print(
                "Sending Groq response to ElevenLabs..."
            )

            if tracker is not None:

                tracker.mark("elevenlabs_start")

            first_byte_marked = False

            def on_first_chunk() -> None:

                nonlocal first_byte_marked

                if (
                    not first_byte_marked
                    and tracker is not None
                ):

                    tracker.mark(
                        "elevenlabs_first_byte"
                    )

                    first_byte_marked = True

            await websocket.send_text(
                json.dumps({
                    "type": "audio_start",
                    "format": "mp3",
                    "request_id": request_id,
                })
            )

            iterator = iter_speech_chunks(
                response,
                on_first_chunk=on_first_chunk,
            )

            def get_next_chunk(
                stream_iterator,
            ):

                try:

                    return next(stream_iterator)

                except StopIteration:

                    return None

            total_bytes = 0

            while True:

                chunk = await asyncio.to_thread(
                    get_next_chunk,
                    iterator,
                )

                if chunk is None:
                    break

                total_bytes += len(chunk)

                await websocket.send_text(
                    json.dumps({
                        "type": "audio_chunk",
                        "data": base64.b64encode(
                            chunk
                        ).decode("utf-8"),
                    })
                )

            if tracker is not None:

                tracker.mark("elevenlabs_end")

            await websocket.send_text(
                json.dumps({
                    "type": "audio_end",
                    "request_id": request_id,
                })
            )

            print(
                "ElevenLabs audio sent to browser:",
                total_bytes,
                "bytes",
            )

        except Exception as error:

            print(
                "ElevenLabs error:",
                error
            )

            await websocket.send_text(
                json.dumps({
                    "type": "error",
                    "text": (
                        "ElevenLabs TTS error: "
                        + str(error)
                    ),
                })
            )

    async def process_user_message(
        user_message,
        request_id: str | None,
    ):

        tracker = (
            latency_trackers.get(request_id)
            if request_id
            else None
        )

        try:

            if tracker is not None:

                tracker.mark("groq_start")

            response = await get_response_async(
                user_message,
                user_id=session_state["id"],
                on_event=emit_event,
            )

            if tracker is not None:

                tracker.mark("groq_end")

            print(
                "Groq:",
                response
            )

            await send_assistant_response(
                response,
                request_id,
            )

        except Exception as error:

            print(
                "Groq error:",
                error
            )

            await websocket.send_text(
                json.dumps({
                    "type": "error",
                    "text": str(error),
                })
            )

    # ========================================================
    # DEEPGRAM API KEY
    # ========================================================

    deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")

    if not deepgram_api_key:

        print("❌ DEEPGRAM_API_KEY not found")

        await websocket.send_text(
            json.dumps({
                "type": "error",
                "text": "DEEPGRAM_API_KEY not found"
            })
        )

        await websocket.close()
        return

    # ========================================================
    # ELEVENLABS API KEY
    # ========================================================

    elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")

    if not elevenlabs_api_key:

        print("❌ ELEVENLABS_API_KEY not found")

        await websocket.send_text(
            json.dumps({
                "type": "error",
                "text": "ELEVENLABS_API_KEY not found"
            })
        )

        await websocket.close()
        return

    # ========================================================
    # CREATE DEEPGRAM CLIENT
    # ========================================================

    try:

        deepgram = AsyncDeepgramClient(
            api_key=deepgram_api_key
        )

        print("✅ Deepgram client created!")

    except Exception as error:

        print(
            "❌ Deepgram client error:",
            error
        )

        await websocket.close()
        return

    # ========================================================
    # DEEPGRAM SESSION STATE (one connection per browser ws)
    # ========================================================

    connection = None
    connect_cm = None
    listen_task = None

    deepgram_open = asyncio.Event()
    deepgram_ready = False
    first_audio_sent = False
    deepgram_error_logged = False
    accept_pcm = True
    finalizing = False

    # ========================================================
    # DEEPGRAM MESSAGE HANDLER
    # ========================================================

    async def handle_deepgram_message(message):

        nonlocal finalizing, accept_pcm
        nonlocal utterance_pcm_open, active_request_id
        nonlocal finalizing_request_id

        try:

            transcript = ""

            if hasattr(message, "channel"):

                channel = message.channel

                if (
                    hasattr(channel, "alternatives")
                    and channel.alternatives
                ):

                    transcript = (
                        channel
                        .alternatives[0]
                        .transcript
                    )

            if not transcript:
                return

            transcript = normalize_transcript(
                transcript
            )

            is_final = getattr(
                message,
                "is_final",
                False
            )

            speech_final = getattr(
                message,
                "speech_final",
                False
            )

            if not is_final and not speech_final:

                tracker = get_active_tracker()

                if (
                    tracker is not None
                    and not tracker.has_mark(
                        "first_interim"
                    )
                ):

                    tracker.mark("first_interim")

            print(
                "Deepgram transcript:",
                transcript
            )

            await websocket.send_text(
                json.dumps({
                    "type": "transcript",
                    "text": transcript,
                    "final": is_final,
                })
            )

            if not (
                is_final
                or speech_final
            ):
                return

            print(
                "Final transcript:",
                transcript
            )

            request_id = (
                finalizing_request_id
                or active_request_id
            )

            finalizing_request_id = None

            tracker = (
                latency_trackers.get(request_id)
                if request_id
                else None
            )

            if tracker is not None:

                tracker.mark("deepgram_final")

            utterance_pcm_open = False

            finalizing = False
            accept_pcm = True

            try:

                await process_user_message(
                    transcript,
                    request_id,
                )

            except Exception as error:

                print(
                    "❌ Groq error:",
                    error
                )

                await websocket.send_text(
                    json.dumps({
                        "type": "error",
                        "text": str(error),
                    })
                )

                return

            return

        except Exception as error:

            print(
                "❌ Deepgram handler error:",
                error
            )

    # ========================================================
    # DEEPGRAM EVENT HANDLERS
    # ========================================================

    def on_open(event):

        nonlocal deepgram_ready

        print("🟢 Deepgram OPEN")

        deepgram_ready = True
        deepgram_open.set()

    def on_message(message):

        try:

            asyncio.create_task(
                handle_deepgram_message(
                    message
                )
            )

        except Exception as error:

            print(
                "❌ Callback error:",
                error
            )

    def on_close(event):

        nonlocal deepgram_ready

        print("🔴 Deepgram CLOSE")

        deepgram_ready = False

    def on_error(error):

        nonlocal deepgram_ready, deepgram_error_logged

        deepgram_ready = False

        if deepgram_error_logged:
            return

        error_text = str(error)

        print(
            "❌ Deepgram ERROR:",
            error
        )

        if "NET-0001" in error_text:

            print(
                "❌ Deepgram NET-0001: connection closed "
                "before audio was received in time"
            )

        deepgram_error_logged = True

    def register_deepgram_handlers(dg_connection):

        dg_connection.on(
            EventType.OPEN,
            on_open
        )

        dg_connection.on(
            EventType.MESSAGE,
            on_message
        )

        dg_connection.on(
            EventType.CLOSE,
            on_close
        )

        dg_connection.on(
            EventType.ERROR,
            on_error
        )

    # ========================================================
    # DEEPGRAM LIFECYCLE
    # ========================================================

    async def cleanup_deepgram():

        nonlocal connection, connect_cm, listen_task
        nonlocal deepgram_ready, deepgram_open

        print("🧹 Deepgram cleaned up")

        if connection is not None:

            try:

                await connection.send_close_stream()

                print("🔴 Deepgram CloseStream sent")

            except Exception as error:

                print(
                    "⚠️ Deepgram CloseStream error:",
                    error
                )

        if listen_task is not None:

            listen_task.cancel()

            try:

                await listen_task

            except asyncio.CancelledError:

                pass

            listen_task = None

        if connect_cm is not None:

            try:

                await connect_cm.__aexit__(None, None, None)

            except Exception as error:

                print(
                    "⚠️ Deepgram context exit error:",
                    error
                )

            connect_cm = None

        connection = None
        deepgram_ready = False
        deepgram_open = asyncio.Event()

    async def ensure_deepgram_connection():

        nonlocal connection, connect_cm, listen_task
        nonlocal deepgram_open, deepgram_ready
        nonlocal deepgram_error_logged, first_audio_sent

        if (
            connection is not None
            and deepgram_ready
        ):
            return True

        if connection is not None and not deepgram_ready:

            await cleanup_deepgram()

        print("🔌 Creating Deepgram connection")

        deepgram_open = asyncio.Event()
        deepgram_error_logged = False
        first_audio_sent = False

        connect_cm = deepgram.listen.v1.connect(
            model="nova-3",
            language="en-US",
            smart_format=True,
            encoding="linear16",
            channels=1,
            sample_rate=16000,
            interim_results=True,
            endpointing=200,
            keyterm=DEEPGRAM_KEYTERMS,
        )

        connection = await connect_cm.__aenter__()

        register_deepgram_handlers(connection)

        print("🎧 Starting Deepgram listener")

        listen_task = asyncio.create_task(
            connection.start_listening()
        )

        try:

            await asyncio.wait_for(
                deepgram_open.wait(),
                timeout=10.0,
            )

        except asyncio.TimeoutError:

            print("❌ Deepgram OPEN timeout")

            await cleanup_deepgram()

            return False

        print("🎤 Deepgram ready for audio")

        return True

    async def forward_pcm_to_deepgram(audio_data):

        nonlocal first_audio_sent, deepgram_error_logged
        nonlocal utterance_pcm_open, active_request_id

        if not audio_data:
            return

        if not accept_pcm:
            return

        if not deepgram_ready or connection is None:

            if not deepgram_error_logged:

                print(
                    "⚠️ Skipping PCM: Deepgram not ready"
                )

                deepgram_error_logged = True

            return

        try:

            if not utterance_pcm_open:

                begin_utterance()

            tracker = get_active_tracker()

            if (
                tracker is not None
                and not tracker.has_mark("first_pcm")
            ):

                tracker.mark("first_pcm")

            if not first_audio_sent:

                print(
                    "First PCM chunk forwarded to Deepgram:",
                    len(audio_data),
                    "bytes"
                )

                first_audio_sent = True

            await connection.send_media(
                audio_data
            )

        except Exception as error:

            if not deepgram_error_logged:

                print(
                    "❌ Deepgram audio error:",
                    error
                )

                if "NET-0001" in str(error):

                    print(
                        "❌ Deepgram NET-0001: stopped "
                        "forwarding audio to closed connection"
                    )

                deepgram_error_logged = True

            await cleanup_deepgram()

    # ========================================================
    # RECEIVE BROWSER DATA
    # ========================================================

    try:

        while True:

            try:

                data = await websocket.receive()

            except WebSocketDisconnect:

                print("🔴 Browser disconnected")

                break

            if data.get("bytes") is not None:

                audio_data = data["bytes"]

                print(
                    "🎵 Received PCM:",
                    len(audio_data),
                    "bytes"
                )

                if not accept_pcm:
                    continue

                if not await ensure_deepgram_connection():

                    if not deepgram_error_logged:

                        await websocket.send_text(
                            json.dumps({
                                "type": "error",
                                "text": (
                                    "Could not open Deepgram "
                                    "connection"
                                ),
                            })
                        )

                        deepgram_error_logged = True

                    continue

                await forward_pcm_to_deepgram(
                    audio_data
                )

            elif data.get("text") is not None:

                message = data["text"]

                try:

                    parsed = json.loads(message)

                except json.JSONDecodeError:

                    parsed = None

                if (
                    isinstance(parsed, dict)
                    and parsed.get("type") == "latency"
                ):

                    if (
                        parsed.get("event")
                        == "playback_start"
                    ):

                        request_id = parsed.get(
                            "request_id"
                        )

                        if not request_id:

                            print(
                                "Latency playback_start "
                                "ignored: missing request_id"
                            )

                            continue

                        tracker = latency_trackers.get(
                            request_id
                        )

                        if tracker is None:

                            print(
                                "Latency playback_start "
                                "ignored: unknown request_id "
                                f"{request_id}"
                            )

                            continue

                        if tracker.has_mark(
                            "playback_start"
                        ):

                            print(
                                "Latency playback_start "
                                "ignored: already recorded for "
                                f"{request_id}"
                            )

                            continue

                        tracker.mark("playback_start")
                        tracker.print_summary()
                        complete_latency(request_id)

                    continue

                if (
                    isinstance(parsed, dict)
                    and parsed.get("type") == "session"
                ):

                    incoming_session_id = parsed.get(
                        "session_id"
                    )

                    if incoming_session_id:

                        unregister_connection(
                            session_state["id"]
                        )

                        session_state["id"] = (
                            incoming_session_id
                        )

                        register_connection(
                            session_state["id"],
                            websocket,
                        )

                        print(
                            "🔁 Session restored:",
                            session_state["id"],
                        )

                    continue

                if (
                    isinstance(parsed, dict)
                    and parsed.get("type") == "finalize"
                ):

                    print("🏁 Finalize received")

                    accept_pcm = False
                    finalizing = True
                    finalizing_request_id = active_request_id
                    utterance_pcm_open = False

                    if (
                        deepgram_ready
                        and connection is not None
                    ):

                        try:

                            await connection.send_finalize()

                            print(
                                "🏁 Deepgram finalize sent"
                            )

                        except Exception as error:

                            if not deepgram_error_logged:

                                print(
                                    "❌ Finalize error:",
                                    error
                                )

                                deepgram_error_logged = True

                    else:

                        print(
                            "⚠️ Finalize ignored: "
                            "no active Deepgram connection"
                        )

                    continue

                user_message = message

                if (
                    isinstance(parsed, dict)
                    and parsed.get("type") == "text"
                ):

                    user_message = parsed.get(
                        "text",
                        ""
                    )

                if not user_message.strip():
                    continue

                request_id = begin_utterance()
                utterance_pcm_open = False

                print(
                    "User text:",
                    user_message
                )

                await process_user_message(
                    user_message,
                    request_id,
                )

    except WebSocketDisconnect:

        print("🔴 Browser disconnected")

    except Exception as error:

        print(
            "❌ SERVER ERROR:",
            error
        )

        try:

            await websocket.send_text(
                json.dumps({
                    "type": "error",
                    "text": str(error),
                })
            )

        except Exception:
            pass

    finally:

        unregister_connection(
            session_state["id"]
        )

        await cleanup_deepgram()

        print("🧹 Connection cleanup complete.")
