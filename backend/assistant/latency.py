import time
from typing import Optional


class LatencyTracker:

    def __init__(self, request_id: str) -> None:

        self.request_id = request_id
        self._utterance_start: Optional[float] = None
        self._marks: dict[str, float] = {}

    def start(self) -> None:

        self._utterance_start = time.perf_counter()
        self._marks.clear()

    def mark(self, name: str) -> None:

        if self._utterance_start is None:
            self.start()

        self._marks[name] = time.perf_counter()

    def has_mark(self, name: str) -> bool:

        return name in self._marks

    def ms_since_utterance_start(
        self,
        name: str,
    ) -> Optional[int]:

        if (
            self._utterance_start is None
            or name not in self._marks
        ):
            return None

        return int(
            (
                self._marks[name]
                - self._utterance_start
            )
            * 1000
        )

    def ms_between(
        self,
        start_name: str,
        end_name: str,
    ) -> Optional[int]:

        if (
            start_name not in self._marks
            or end_name not in self._marks
        ):
            return None

        return int(
            (
                self._marks[end_name]
                - self._marks[start_name]
            )
            * 1000
        )

    def _fmt(self, value: Optional[int]) -> str:

        if value is None:
            return "n/a"

        return f"{value} ms"

    def print_summary(self) -> None:

        if self._utterance_start is None:
            return

        first_pcm = self.ms_since_utterance_start(
            "first_pcm"
        )
        first_interim = self.ms_since_utterance_start(
            "first_interim"
        )
        deepgram_final = self.ms_since_utterance_start(
            "deepgram_final"
        )

        groq = self.ms_between(
            "deepgram_final",
            "groq_end",
        )

        if groq is None:
            groq = self.ms_since_utterance_start(
                "groq_end"
            )

        elevenlabs_first = self.ms_between(
            "groq_end",
            "elevenlabs_first_byte",
        )

        playback_start = self.ms_since_utterance_start(
            "playback_start"
        )

        deepgram_processing = deepgram_final

        groq_processing = self.ms_between(
            "deepgram_final",
            "groq_end",
        )

        if groq_processing is None:
            groq_processing = self.ms_since_utterance_start(
                "groq_end"
            )

        elevenlabs_ttfb = self.ms_between(
            "groq_end",
            "elevenlabs_first_byte",
        )

        browser_playback = self.ms_between(
            "elevenlabs_end",
            "playback_start",
        )

        print("========== LATENCY ==========")
        print(f"Request ID:          {self.request_id}")

        print(
            f"First PCM:           "
            f"{self._fmt(first_pcm)}"
        )

        print(
            f"First interim:       "
            f"{self._fmt(first_interim)}"
        )

        print(
            f"Deepgram final:      "
            f"{self._fmt(deepgram_final)}"
        )

        print(
            f"Groq:                "
            f"{self._fmt(groq)}"
        )

        print(
            f"ElevenLabs first:    "
            f"{self._fmt(elevenlabs_first)}"
        )

        print(
            f"Playback start:      "
            f"{self._fmt(playback_start)}"
        )

        print(
            f"TOTAL:               "
            f"{self._fmt(playback_start)}"
        )

        print("=============================")

        print(
            f"Deepgram processing: "
            f"{self._fmt(deepgram_processing)}"
        )

        print(
            f"Groq processing:     "
            f"{self._fmt(groq_processing)}"
        )

        print(
            f"ElevenLabs TTFB:     "
            f"{self._fmt(elevenlabs_ttfb)}"
        )

        print(
            f"Browser playback:    "
            f"{self._fmt(browser_playback)}"
        )

        print(
            "Stage timestamps (ms since utterance start):"
        )

        for stage_name in (
            "first_pcm",
            "first_interim",
            "deepgram_final",
            "groq_start",
            "groq_end",
            "elevenlabs_start",
            "elevenlabs_first_byte",
            "elevenlabs_end",
            "playback_start",
        ):

            if stage_name in self._marks:

                print(
                    f"  {stage_name}: "
                    f"{self.ms_since_utterance_start(stage_name)}"
                )
