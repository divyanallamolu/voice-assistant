import os
from typing import Callable, Iterator, Optional

from elevenlabs.client import ElevenLabs
from dotenv import load_dotenv


load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

if not ELEVENLABS_API_KEY:
    raise RuntimeError("ELEVENLABS_API_KEY not found in .env")

elevenlabs = ElevenLabs(
    api_key=ELEVENLABS_API_KEY
)

ELEVENLABS_MODEL = "eleven_flash_v2_5"
ELEVENLABS_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"
ELEVENLABS_OUTPUT_FORMAT = "mp3_44100_128"


def iter_speech_chunks(
    text: str,
    on_first_chunk: Optional[Callable[[], None]] = None,
) -> Iterator[bytes]:

    audio_stream = elevenlabs.text_to_speech.stream(
        voice_id=ELEVENLABS_VOICE_ID,
        text=text,
        model_id=ELEVENLABS_MODEL,
        output_format=ELEVENLABS_OUTPUT_FORMAT,
        optimize_streaming_latency=3,
    )

    first_chunk = True

    for chunk in audio_stream:

        if not chunk:
            continue

        if first_chunk:

            if on_first_chunk is not None:
                on_first_chunk()

            first_chunk = False

        yield chunk


def text_to_speech(text: str) -> bytes:

    print("ElevenLabs generating speech...")

    audio_data = bytearray()

    for chunk in iter_speech_chunks(text):

        audio_data.extend(chunk)

    print(
        "ElevenLabs audio generated:",
        len(audio_data),
        "bytes",
    )

    return bytes(audio_data)
