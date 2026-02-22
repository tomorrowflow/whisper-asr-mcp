#!/usr/bin/env python3
"""Quick test script to transcribe audio."""

import asyncio
import base64
import os
import sys

# Set environment variables before importing server
os.environ["WHISPER_ASR_URL"] = "http://192.168.2.15:9000"
os.environ["FFMPEG_API_URL"] = "http://192.168.2.16:3030"

sys.path.insert(0, "/home/openclaw/whisper-asr-mcp/src")
from server import transcribe


async def test_with_base64():
    """Test transcription using base64-encoded audio."""
    print("Testing with base64...")
    audio_path = "/home/openclaw/audio.m4a"

    with open(audio_path, "rb") as f:
        audio_data = f.read()

    audio_base64 = base64.b64encode(audio_data).decode("utf-8")

    result = await transcribe(
        audio_base64=audio_base64,
        audio_url=None,
        audio_path=None,
        filename="audio.m4a",
        output_format="text",
    )
    print(f"Result: {result}")
    return result


async def test_with_path():
    """Test transcription using local file path."""
    print("\nTesting with audio_path...")
    result = await transcribe(
        audio_base64=None,
        audio_url=None,
        audio_path="/home/openclaw/audio.m4a",
        filename=None,
        output_format="text",
    )
    print(f"Result: {result}")
    return result


async def main():
    await test_with_base64()
    await test_with_path()


if __name__ == "__main__":
    asyncio.run(main())
