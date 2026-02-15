# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Bruno: An AI-powered pipeline that takes audioless videos and generates context-aware audio/music using Google Cloud Video Intelligence, OpenAI GPT-4o, and Suno AI.

**Architecture**: Next.js frontend → FastAPI backend → AI pipeline (GCP → OpenAI → Suno → FFmpeg)

## Development Commands

### Frontend (Next.js)
```bash
cd frontend
npm run dev      # Start dev server on http://localhost:3000
npm run build    # Production build
npm run lint     # Run ESLint
```

### Backend (FastAPI)
```bash
cd backend
python main.py   # Start uvicorn server on http://localhost:8000
# Or manually:
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Backend Debug Endpoints
```bash
# Test only GCP video analysis
curl -X POST http://localhost:8000/api/analyze-only -F "video=@path/to/video.mp4"

# Test GCP analysis + OpenAI prompt generation
curl -X POST http://localhost:8000/api/prompt-only -F "video=@path/to/video.mp4"

# Serve output files directly
curl http://localhost:8000/api/outputs/output_filename.mp4 --output test.mp4
```

## AI Pipeline Architecture

The processing pipeline follows this sequence:

1. **Video Upload** (`/api/generate` POST)
   - Validates video file type
   - Saves to temporary file
   - Gets video duration using moviepy

2. **GCP Video Intelligence** (`api/gcp_video_analysis.py`)
   - Uploads video to GCS bucket: `soundscape-ai-uploads-shivam`
   - Analyzes using REST transport (not gRPC) to avoid firewall issues
   - Features: LABEL_DETECTION, SHOT_CHANGE_DETECTION, OBJECT_TRACKING
   - Returns structured context with scene breakdown, labels, and tracked objects
   - Auto-cleans up GCS file after analysis

3. **OpenAI Prompt Generation** (`api/openai_prompt.py`)
   - Uses GPT-4o with strict system prompt (temperature 0.75)
   - Generates genre-authentic lyrics describing visible actions (not emotions)
   - Creates section-based music structure with precise timestamps
   - Emphasizes duration control (mentioned 4+ times in prompt)
   - Extracts positive tags and generates negative tags to avoid unwanted styles
   - Returns: `{prompt, tags, negative_tags}`

4. **Suno Audio Generation** (`api/suno_generate.py`)
   - Uses official TreeHacks API: `https://studio-api.prod.suno.com/api/v2/external/hackathons`
   - Submits generation with prompt, tags, negative_tags, make_instrumental flag
   - Polls `/clips?ids=...` every 5s until status is "complete" (max 300s)
   - Downloads audio file (mp3/wav) to temp location
   - Note: Suno API has NO duration parameter - duration control is via prompt text

5. **Media Combination** (`api/combine_media.py`)
   - Uses moviepy to merge video + audio
   - Trims audio if longer than video
   - Outputs with codec: libx264 (video), aac (audio)
   - Returns final video file

6. **Response**
   - Copies output to `backend/outputs/` directory
   - Returns entire video file as Response (not StreamingResponse for better browser compatibility)
   - Includes cache-control headers to prevent stale playback

## Environment Variables Required

Create `backend/.env` with:
```bash
GOOGLE_APPLICATION_CREDENTIALS=/path/to/gcp-service-account.json
OPENAI_API_KEY=sk-...
SUNO_API_KEY=...
```

Frontend can optionally set:
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000  # defaults to this if not set
```

## Key Technical Patterns

### Async/Await Throughout
All API functions in backend are `async` - use `await` when calling them.

### Error Handling
- Each pipeline step has try/except wrapping
- HTTPException raised for client errors (400/500)
- Temp files cleaned up in finally blocks
- GCS blobs deleted after analysis

### Video Transport
- Backend uses `Response` (not `StreamingResponse`) to return full video bytes
- Frontend creates blob URL from response for reliable browser playback
- Headers include: `Content-Disposition: inline`, `Accept-Ranges: bytes`, cache-control

### Frontend State Management
- Uses React hooks (no external state library)
- Pipeline steps tracked: idle → uploading → analyzing → prompting → generating → combining → done
- Progress simulation (15s intervals) since backend is single long-running endpoint

## Important Context

### GCP Video Intelligence
- Must use REST transport: `VideoIntelligenceServiceClient(transport="rest")`
- Timeout handling: polls every 5s, max 5 minutes
- Returns rich context: shot annotations, labels per scene, object tracking with confidence scores

### OpenAI Prompt Engineering
- System prompt is 150+ lines enforcing strict rules
- Focus: genre authenticity, scene-grounded lyrics, duration control
- Avoid: emotional labels, music references in lyrics, abstract poetry
- Structure: [Section Name] followed by "Genre, Instrument, Vocal, BPM" format

### Suno API Specifics
- No duration parameter in API - must emphasize duration heavily in prompt text
- Status flow: submitted → streaming → complete
- Two separate calls: POST `/generate` then poll GET `/clips?ids=...`
- Returns audio_url when complete

### Known Issues (from DIAGNOSIS.md)
- Video display initially had issues with StreamingResponse - fixed by using Response
- Blob creation requires non-zero size check
- FFmpeg must use H.264 codec for browser compatibility

## Directory Structure

```
/backend
  /api
    gcp_video_analysis.py    # GCP Video Intelligence integration
    openai_prompt.py         # GPT-4o prompt generation with strict rules
    suno_generate.py         # Suno AI audio generation (TreeHacks API)
    combine_media.py         # moviepy video+audio merger
  main.py                    # FastAPI server with /api/generate endpoint
  requirements.txt           # Python dependencies
  .env                       # API keys (not in repo)
  /uploads                   # Temp upload directory
  /outputs                   # Final output videos

/frontend
  /src
    /app
      page.tsx               # Main UI with upload, pipeline status, output
      layout.tsx             # Root layout
    /components/ui           # shadcn/ui components (button, card, progress)
  package.json               # npm dependencies (Next.js 16, React 19, Tailwind 4)
```

## Testing the Pipeline

1. Start backend: `cd backend && python main.py`
2. Start frontend: `cd frontend && npm run dev`
3. Upload a video at http://localhost:3000
4. Watch browser console for detailed logging: blob creation, video loading
5. Check backend terminal for pipeline stage logs with "=" separators
6. Output saved to `backend/outputs/output_<filename>.mp4`
