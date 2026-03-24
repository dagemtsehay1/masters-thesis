import queue
import json
from typing import Optional

import sounddevice as sd
from vosk import Model, KaldiRecognizer


COMMANDS = ["go", "back", "stop", "left", "right"]


class VoiceCommandDetector:
    def __init__(self, model_path: str):
        self.q: queue.Queue[bytes] = queue.Queue()
        self.model = Model(model_path)
        self.recognizer = KaldiRecognizer(self.model, 16000)

    def _callback(self, indata, frames, time, status):
        if status:
            print(status)
        self.q.put(bytes(indata))

    def listen(self) -> Optional[str]:
        data = self.q.get()

        if self.recognizer.AcceptWaveform(data):
            result = json.loads(self.recognizer.Result())
            text = result.get("text", "").lower()

            if text:
                print(f"🗣 Heard: {text}")

            for cmd in COMMANDS:
                if cmd in text:
                    return cmd

        return None

    def start_stream(self):
        return sd.RawInputStream(
            samplerate=16000,
            blocksize=8000,
            dtype="int16",
            channels=1,
            callback=self._callback,
        )