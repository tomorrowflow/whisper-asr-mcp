# whisper-asr-mcp

An MCP (Model Context Protocol) server that transcribes audio to text using OpenAI's Whisper model. Supports automatic format conversion via ffmpeg and language detection.

## Features

- Transcribe audio from file paths, URLs, or base64-encoded data
- Automatic conversion of any ffmpeg-supported format to MP3
- Language auto-detection for optimal transcription accuracy
- Multiple output formats: plain text, JSON, SRT, VTT, TSV

## Prerequisites

- [Whisper ASR WebService](https://github.com/ahmetoner/whisper-asr-webservice) running and accessible
- [ffmpeg-api](https://github.com/jrottenberg/ffmpeg) or compatible HTTP ffmpeg service for format conversion
- Python 3.11+ (or Docker)

## Setup

### Docker (recommended)

1. Copy the example environment file and configure it:

```bash
cp .env.example .env
```

2. Edit `.env` with your service URLs:

```
WHISPER_ASR_URL=http://your-whisper-host:9000
FFMPEG_API_URL=http://your-ffmpeg-host:3000
MCP_PORT=3020
```

3. Run with Docker Compose:

```bash
docker compose up -d
```

### Manual

1. Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set environment variables and run:

```bash
export WHISPER_ASR_URL=http://your-whisper-host:9000
export FFMPEG_API_URL=http://your-ffmpeg-host:3000
python -m src.server
```

## MCP Tool Usage

The server exposes a single `transcribe` tool. Provide exactly one audio source:

**From a file path:**
```
transcribe(audio_path="/media/inbound/recording.m4a")
```

**From a URL:**
```
transcribe(audio_url="https://example.com/audio.mp3")
```

**From base64 data:**
```
transcribe(audio_base64="SGVsbG8gV29ybGQ=...", filename="audio.m4a")
```

### Output Formats

Specify `output_format` to change the response format:

| Format | Description |
|--------|-------------|
| `text` | Plain text transcription (default) |
| `json` | JSON with word-level timestamps |
| `srt`  | SRT subtitle format |
| `vtt`  | WebVTT subtitle format |
| `tsv`  | Tab-separated values |

### Response

```json
{
  "transcription": "Hello, world.",
  "detected_language": "en",
  "output_format": "text"
}
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `WHISPER_ASR_URL` | `http://localhost:9000` | Whisper ASR WebService URL |
| `FFMPEG_API_URL` | `http://localhost:3000` | ffmpeg API service URL |
| `MCP_HOST` | `0.0.0.0` | Host to bind the MCP server |
| `MCP_PORT` | `3020` | Port for the MCP server |
