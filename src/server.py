"""Whisper ASR MCP Server with HTTP transport."""

import base64
import os
from enum import Enum
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

# Configuration from environment
WHISPER_ASR_URL = os.getenv("WHISPER_ASR_URL", "http://localhost:9000")
FFMPEG_API_URL = os.getenv("FFMPEG_API_URL", "http://192.168.2.16:3030")
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "3020"))

# MCP Server Instructions
MCP_INSTRUCTIONS = """
# Whisper ASR MCP Server Instructions

## Overview
Audio transcription service with automatic format conversion and language detection.
Converts speech to text using OpenAI's Whisper model.

## Tool Usage

### `transcribe` Tool
Transcribes audio files to text. Provide exactly ONE audio source:

**From file path (most common):**
```
transcribe(audio_path="/media/inbound/recording.m4a")
```

**From URL:**
```
transcribe(audio_url="https://example.com/audio.mp3")
```

**From base64 data:**
```
transcribe(audio_base64="SGVsbG8gV29ybGQ=...")
```

### Output Formats
- `text` (default): Plain text transcription
- `json`: JSON with word-level timestamps
- `srt`: SRT subtitle format
- `vtt`: WebVTT subtitle format
- `tsv`: Tab-separated values

**Example with format:**
```
transcribe(audio_path="/media/inbound/video.mp4", output_format="srt")
```

## Response Structure
Returns a dictionary:
- `transcription`: The transcribed text/content
- `detected_language`: Auto-detected language code (e.g., "en")
- `output_format`: The format used

## Best Practices
1. Use `audio_path` for files in `/media/inbound/`
2. Language is auto-detected - no need to specify
3. Any ffmpeg-supported format works (mp3, wav, m4a, flac, webm, etc.)
4. Long files may take several minutes - be patient
5. For subtitles, use `srt` or `vtt` output formats

## Error Handling
Errors return `{"error": "description"}`. Common issues:
- File not found: Check the path exists
- Conversion failed: Audio may be corrupted
- Transcription failed: Service may be unavailable
"""

# Initialize MCP server
mcp = FastMCP(
    name="Whisper ASR",
    instructions=MCP_INSTRUCTIONS,
    host=MCP_HOST,
    port=MCP_PORT,
)


class OutputFormat(str, Enum):
    """Supported transcription output formats."""
    TEXT = "text"
    JSON = "json"
    VTT = "vtt"
    SRT = "srt"
    TSV = "tsv"


class TranscriptionResult(BaseModel):
    """Result of audio transcription."""
    text: str
    detected_language: Optional[str] = None
    output_format: str


# Audio formats that whisper-asr can handle directly (via its internal ffmpeg)
# However, faster_whisper has issues with some formats, so we convert everything non-mp3
MP3_SIGNATURES = [
    b'\xff\xfb',  # MP3 frame sync
    b'\xff\xfa',  # MP3 frame sync
    b'\xff\xf3',  # MP3 frame sync
    b'\xff\xf2',  # MP3 frame sync
    b'ID3',       # ID3v2 tag
]


def is_mp3(audio_data: bytes) -> bool:
    """Check if audio data is MP3 format based on magic bytes."""
    for sig in MP3_SIGNATURES:
        if audio_data.startswith(sig):
            return True
    return False


async def convert_to_mp3(audio_data: bytes, filename: str = "audio") -> bytes:
    """Convert audio to MP3 using ffmpeg-api service."""
    async with httpx.AsyncClient(timeout=300.0) as client:
        # Determine a reasonable filename extension for the input
        files = {"file": (filename, audio_data)}
        response = await client.post(
            f"{FFMPEG_API_URL}/convert/audio/to/mp3",
            files=files,
        )
        response.raise_for_status()
        return response.content


async def detect_language(audio_data: bytes) -> Optional[str]:
    """Detect language of audio using whisper-asr service."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        files = {"audio_file": ("audio.mp3", audio_data, "audio/mpeg")}
        response = await client.post(
            f"{WHISPER_ASR_URL}/detect-language",
            files=files,
        )
        if response.status_code == 200:
            result = response.json()
            # Response format: {"detected_language": "en", "language_code": "en"}
            return result.get("language_code") or result.get("detected_language")
        return None


async def transcribe_audio_data(
    audio_data: bytes,
    language: Optional[str] = None,
    output_format: OutputFormat = OutputFormat.TEXT,
) -> str:
    """Transcribe audio using whisper-asr service."""
    async with httpx.AsyncClient(timeout=600.0) as client:
        files = {"audio_file": ("audio.mp3", audio_data, "audio/mpeg")}
        params = {"output": output_format.value}
        if language:
            params["language"] = language

        response = await client.post(
            f"{WHISPER_ASR_URL}/asr",
            files=files,
            params=params,
        )
        response.raise_for_status()

        # Return based on output format
        if output_format == OutputFormat.JSON:
            return response.text  # Already JSON string
        return response.text


async def fetch_audio_from_url(url: str) -> tuple[bytes, str]:
    """Fetch audio from URL, return data and filename."""
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()

        # Try to get filename from URL or content-disposition
        filename = url.split("/")[-1].split("?")[0] or "audio"
        if "content-disposition" in response.headers:
            cd = response.headers["content-disposition"]
            if "filename=" in cd:
                filename = cd.split("filename=")[-1].strip('"\'')

        return response.content, filename


@mcp.tool()
async def transcribe(
    audio_base64: Optional[str] = Field(
        default=None,
        description="Base64-encoded audio data. Provide either this, audio_url, or audio_path.",
    ),
    audio_url: Optional[str] = Field(
        default=None,
        description="URL to fetch audio from. Provide either this, audio_base64, or audio_path.",
    ),
    audio_path: Optional[str] = Field(
        default=None,
        description="Local file path to read audio from. Provide either this, audio_base64, or audio_url.",
    ),
    output_format: str = Field(
        default="text",
        description="Output format: 'text' (default), 'json', 'vtt', 'srt', or 'tsv'.",
    ),
    filename: Optional[str] = Field(
        default=None,
        description="Original filename with extension, helps with format detection.",
    ),
) -> dict:
    """
    Transcribe audio to text with automatic format conversion and language detection.

    Accepts audio in any format supported by ffmpeg. Non-MP3 files are automatically
    converted to MP3 before transcription. Language is auto-detected and used for
    optimal transcription accuracy.

    Returns transcription in the requested format (text, json, vtt, srt, or tsv).
    """
    # Validate input - exactly one source must be provided
    sources = [audio_base64, audio_url, audio_path]
    provided_sources = sum(1 for s in sources if s)

    if provided_sources == 0:
        return {"error": "Provide one of: audio_base64, audio_url, or audio_path"}

    if provided_sources > 1:
        return {"error": "Provide only one of: audio_base64, audio_url, or audio_path"}

    # Parse output format
    try:
        fmt = OutputFormat(output_format.lower())
    except ValueError:
        return {"error": f"Invalid output_format. Choose from: {[f.value for f in OutputFormat]}"}

    # Get audio data
    try:
        if audio_base64:
            audio_data = base64.b64decode(audio_base64)
            filename = filename or "audio"
        elif audio_path:
            if not os.path.exists(audio_path):
                return {"error": f"File not found: {audio_path}"}
            with open(audio_path, "rb") as f:
                audio_data = f.read()
            filename = filename or os.path.basename(audio_path)
        else:
            audio_data, detected_filename = await fetch_audio_from_url(audio_url)
            filename = filename or detected_filename
    except Exception as e:
        return {"error": f"Failed to get audio data: {str(e)}"}

    # Convert to MP3 if needed
    try:
        if not is_mp3(audio_data):
            audio_data = await convert_to_mp3(audio_data, filename)
    except Exception as e:
        return {"error": f"Failed to convert audio to MP3: {str(e)}"}

    # Detect language
    detected_language = None
    try:
        detected_language = await detect_language(audio_data)
    except Exception:
        # Language detection failed, proceed without it
        pass

    # Transcribe
    try:
        transcription = await transcribe_audio_data(audio_data, detected_language, fmt)
    except Exception as e:
        return {"error": f"Transcription failed: {str(e)}"}

    return {
        "transcription": transcription,
        "detected_language": detected_language,
        "output_format": fmt.value,
    }


if __name__ == "__main__":
    # Run with Streamable HTTP transport (single POST endpoint at /mcp)
    mcp.run(transport="streamable-http")
