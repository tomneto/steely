"""
Streaming STT with steely.stt — switching provider is a one-line change.

The whole point of steely.stt: the session API and the events you receive are
identical across backends. Only the ``STTClient(...)`` construction differs.

Run (no real backend needed — uses the in-memory "fake" provider by default):
    python examples/stt_streaming.py

Point it at a real backend by setting STT_PROVIDER + that provider's env vars:
    pip install "steely[stt-deepgram]"
    export STT_PROVIDER=deepgram DEEPGRAM_API_KEY=dg_xxx
    python examples/stt_streaming.py

    pip install "steely[stt-assemblyai]"
    export STT_PROVIDER=assemblyai ASSEMBLYAI_API_KEY=aai_xxx
    python examples/stt_streaming.py

The worker always pushes the RAW frame bytes it gets from LiveKit
(``frame.data.tobytes()``); the adapter resamples/transcodes internally.
"""
import asyncio
import os

from steely.stt import STTClient, STTConfig


def build_client() -> STTClient:
    """Pick the provider from config. This is the ONLY provider-specific code."""
    provider = os.environ.get("STT_PROVIDER", "fake").lower()
    if provider == "deepgram":
        return STTClient("deepgram", api_key=os.environ["DEEPGRAM_API_KEY"])
    if provider == "assemblyai":
        return STTClient("assemblyai", api_key=os.environ["ASSEMBLYAI_API_KEY"])
    if provider in ("google", "chirp"):
        return STTClient(provider)  # GOOGLE_APPLICATION_CREDENTIALS from env
    if provider == "azure":
        return STTClient(
            "azure",
            subscription_key=os.environ["AZURE_SPEECH_KEY"],
            region=os.environ["AZURE_SPEECH_REGION"],
        )
    if provider in ("aws", "transcribe"):
        return STTClient(provider, region=os.environ.get("AWS_REGION", "us-east-1"))
    if provider in ("whisperlive", "whisper"):
        # Self-hosted faster-whisper; WHISPERLIVE_URL defaults to ws://localhost:9090.
        return STTClient(provider, endpoint_url=os.environ.get("WHISPERLIVE_URL"))
    return STTClient("fake")  # no network, scripted events


def fake_frames():
    """Stand-in for LiveKit frames: 20 ms of silence @ 16 kHz mono s16le."""
    for _ in range(10):
        yield b"\x00\x00" * 320


async def main() -> None:
    client = build_client()
    print("provider:", client.provider_name)

    # sample_rate/encoding describe the frames the worker WILL push.
    config = STTConfig(language="pt-BR", sample_rate=16000, encoding="pcm_s16le", channels=1)
    session = await client.open_session(config)

    async with session:
        for frame in fake_frames():
            await session.push_frame(frame)      # raw bytes from LiveKit
        await session.end_input()
        async for event in session:              # interim... final — uniform everywhere
            marker = "FINAL" if event.is_final else "  ..."
            print(f"[{marker}] {event.start:>5}-{event.end:<5}ms  {event.text!r}")


if __name__ == "__main__":
    asyncio.run(main())
