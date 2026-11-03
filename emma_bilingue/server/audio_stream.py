import base64
import numpy as np
import asyncio
from typing import AsyncGenerator, Optional
import sounddevice as sd
import queue
import threading

class AudioStreamer:
    def __init__(self, sample_rate: int = 24000):
        self.sample_rate = sample_rate
        self.chunk_size = 1024

    async def stream_audio_chunks(self, audio: np.ndarray,
                                   chunk_duration_ms: int = 50) -> AsyncGenerator[str, None]:
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        if np.max(np.abs(audio)) > 1.0:
            audio = audio / np.max(np.abs(audio))

        audio_int16 = (audio * 32767).astype(np.int16)
        samples_per_chunk = int(self.sample_rate * 0.05)

        for i in range(0, len(audio_int16), samples_per_chunk):
            chunk = audio_int16[i:i + samples_per_chunk]
            if len(chunk) == 0:
                continue

            chunk_bytes = chunk.tobytes()
            chunk_b64 = base64.b64encode(chunk_bytes).decode('utf-8')

            yield chunk_b64
            await asyncio.sleep(0.01)

    def encode_audio_chunk(self, audio_chunk: np.ndarray) -> str:
        if audio_chunk.dtype != np.int16:
            audio_chunk = (audio_chunk * 32767).astype(np.int16)
        return base64.b64encode(audio_chunk.tobytes()).decode('utf-8')


class MicrophoneStream:
    def __init__(self, sample_rate: int = 16000, chunk_size: int = 512):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.channels = 1
        self._queue = asyncio.Queue()
        self._stream = None
        self._running = False

    async def start(self):
        self._running = True
        loop = asyncio.get_event_loop()

        def callback(indata, frames, time_info, status):
            if status:
                print(f"Audio status: {status}")
            asyncio.run_coroutine_threadsafe(
                self._queue.put(indata.copy()), loop
            )

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            blocksize=self.chunk_size,
            callback=callback
        )
        self._stream.start()

    async def get_audio_chunk(self) -> np.ndarray:
        return await self._queue.get()

    async def stop(self):
        self._running = False
        if self._stream:
            self._stream.stop()
            self._stream.close()