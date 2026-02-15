"""
Main FastAPI server.
Orchestrates the full pipeline: Video → GCP Analysis → OpenAI Prompt → Suno Audio → Combined Output.
"""

import os
import shutil
import tempfile
import traceback
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import json
import asyncio
from typing import AsyncGenerator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from api.gcp_video_analysis import analyze_video
from api.openai_prompt import generate_suno_prompt
from api.suno_generate import generate_audio
from api.combine_media import combine_video_audio, get_video_duration

# Load environment variables from .env file
load_dotenv()

# Rate limiting configuration
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Bruno",
    description="Takes an audioless video and generates context-aware audio using AI",
    version="1.0.0",
)

# Add rate limit exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS - allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3005", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure upload/output directories exist (use absolute paths)
UPLOAD_DIR = Path("uploads").absolute()
OUTPUT_DIR = Path("outputs").absolute()
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


@app.get("/")
async def health_check():
    return {"status": "ok", "message": "Bruno API is running"}


async def progress_generator(video_path: str, video_filename: str) -> AsyncGenerator[str, None]:
    """Generator that yields SSE progress updates during video processing."""

    def send_event(stage: str, message: str, progress: int) -> str:
        """Helper to format SSE event."""
        data = json.dumps({"stage": stage, "message": message, "progress": progress})
        return f"data: {data}\n\n"

    temp_video_path = video_path
    output_path = None

    try:
        # Initial upload complete
        yield send_event("uploading", "Video uploaded successfully", 10)
        await asyncio.sleep(0.1)

        # Get duration and validate
        duration = get_video_duration(temp_video_path)

        # VIDEO DURATION LIMIT: Maximum 60 seconds
        if duration > 60:
            raise ValueError(f"Video is too long ({duration:.1f}s). Maximum allowed duration is 60 seconds.")

        # Step 1: GCP Analysis
        yield send_event("analyzing", "Analyzing video with Google Cloud AI...", 15)

        video_context = await analyze_video(temp_video_path)

        yield send_event("analyzing", "Video analysis complete", 35)
        await asyncio.sleep(0.1)

        # Step 2: OpenAI Prompt
        yield send_event("prompting", "Crafting music prompt with OpenAI...", 40)

        prompt_result = await generate_suno_prompt(video_context, duration)

        yield send_event("prompting", "Music prompt generated", 55)
        await asyncio.sleep(0.1)

        # Step 3: Suno Generation
        yield send_event("generating", "Generating audio with Suno AI...", 60)

        audio_path = await generate_audio(
            prompt=prompt_result["prompt"],
            tags=prompt_result["tags"],
            duration=duration,
            negative_tags=prompt_result.get("negative_tags"),
        )

        yield send_event("generating", "Audio generated successfully", 80)
        await asyncio.sleep(0.1)

        # Step 4: Combine
        yield send_event("combining", "Combining video and audio...", 85)

        output_path = await combine_video_audio(temp_video_path, audio_path)

        # Copy to outputs
        safe_filename = Path(video_filename).stem if video_filename else "output"
        final_output = OUTPUT_DIR / f"output_{safe_filename}.mp4"
        shutil.copy2(output_path, final_output)

        # Clean up temp files
        if os.path.exists(audio_path):
            os.unlink(audio_path)
        if os.path.exists(output_path):
            os.unlink(output_path)

        yield send_event("done", f"Complete! File: {final_output.name}", 100)

    except Exception as e:
        print(f"[SSE] Error in progress_generator: {e}")
        traceback.print_exc()
        error_data = json.dumps({"stage": "error", "message": str(e), "progress": 0})
        yield f"data: {error_data}\n\n"

    finally:
        if temp_video_path and os.path.exists(temp_video_path):
            try:
                os.unlink(temp_video_path)
            except:
                pass


@app.post("/api/generate-stream")
@limiter.limit("3/hour")  # Maximum 3 videos per hour per IP
async def generate_video_with_audio_stream(request: Request, video: UploadFile = File(...)):
    """
    Streaming endpoint that sends real-time progress updates via SSE.
    Rate limited to 3 requests per hour per IP address.
    """
    if not video.content_type or not video.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Please upload a valid video file")

    # Save uploaded video
    suffix = Path(video.filename).suffix if video.filename else ".mp4"
    temp_video = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="upload_")
    content = await video.read()
    temp_video.write(content)
    temp_video.close()

    return StreamingResponse(
        progress_generator(temp_video.name, video.filename),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.post("/api/generate")
@limiter.limit("3/hour")  # Maximum 3 videos per hour per IP
async def generate_video_with_audio(request: Request, video: UploadFile = File(...)):
    """
    Main pipeline endpoint.
    Rate limited to 3 requests per hour per IP address.

    1. Receives an audioless video
    2. Analyzes it with Google Cloud Video Intelligence
    3. Generates a music prompt with OpenAI
    4. Creates audio with Suno
    5. Combines video + audio
    6. Returns the final video
    """
    # Validate file type
    if not video.content_type or not video.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Please upload a valid video file")

    temp_video_path = None
    output_path = None

    try:
        # Save uploaded video to temp file
        suffix = Path(video.filename).suffix if video.filename else ".mp4"
        temp_video = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="upload_")
        content = await video.read()
        temp_video.write(content)
        temp_video.close()
        temp_video_path = temp_video.name

        print(f"[Pipeline] Video saved: {temp_video_path} ({len(content)} bytes)")

        # Get video duration for timing context
        duration = get_video_duration(temp_video_path)
        print(f"[Pipeline] Video duration: {duration:.1f}s")

        # VIDEO DURATION LIMIT: Maximum 60 seconds
        if duration > 60:
            raise HTTPException(
                status_code=400,
                detail=f"Video is too long ({duration:.1f}s). Maximum allowed duration is 60 seconds."
            )

        # Step 1: Analyze video with GCP
        print("\n" + "=" * 50)
        print("STEP 1: Analyzing video with Google Cloud...")
        print("=" * 50)
        try:
            video_context = await analyze_video(temp_video_path)
            print("\n[Pipeline] === GCP VIDEO CONTEXT OUTPUT ===")
            print(video_context)
            print("==========================================\n")
        except Exception as e:
            print(f"[Pipeline] Error in GCP Analysis: {e}")
            raise HTTPException(status_code=500, detail=f"GCP Analysis failed: {str(e)}")

        # Step 2: Generate Suno prompt with OpenAI
        print("\n" + "=" * 50)
        print("STEP 2: Generating music prompt with OpenAI...")
        print("=" * 50)
        try:
            prompt_result = await generate_suno_prompt(video_context, duration)
            print("\n[Pipeline] === OPENAI SUNO PROMPT OUTPUT ===")
            print(prompt_result['prompt'])
            print("--------------------------------------------")
            print(f"Tags: {prompt_result['tags']}")
            print(f"Negative Tags: {prompt_result.get('negative_tags', 'None')}")
            print("============================================\n")
        except Exception as e:
            print(f"[Pipeline] Error in OpenAI Prompt Generation: {e}")
            raise HTTPException(status_code=500, detail=f"OpenAI Prompt Generation failed: {str(e)}")

        # Step 3: Generate audio with Suno
        print("\n" + "=" * 50)
        print("STEP 3: Generating audio with Suno...")
        print("=" * 50)
        try:
            audio_path = await generate_audio(
                prompt=prompt_result["prompt"],
                tags=prompt_result["tags"],
                duration=duration,
                negative_tags=prompt_result.get("negative_tags"),
            )
            print(f"[Pipeline] Audio generated successfully: {audio_path}")
        except Exception as e:
            print(f"[Pipeline] Error in Suno Audio Generation: {e}")
            raise HTTPException(status_code=500, detail=f"Suno Audio Generation failed: {str(e)}")

        # Step 4: Combine video + audio
        print("\n" + "=" * 50)
        print("STEP 4: Combining video and audio...")
        print("=" * 50)
        try:
            output_path = await combine_video_audio(temp_video_path, audio_path)
            print(f"[Pipeline] Final video created at: {output_path}")
        except Exception as e:
            print(f"[Pipeline] Error in Media Combination: {e}")
            raise HTTPException(status_code=500, detail=f"Media Combination failed: {str(e)}")

        # Copy to outputs dir for serving
        safe_filename = Path(video.filename).stem if video.filename else "output"
        final_output = OUTPUT_DIR / f"output_{safe_filename}.mp4"

        print(f"[Pipeline] Copying output to: {final_output}")
        shutil.copy2(output_path, final_output)

        # Verify the file exists and has content
        if not final_output.exists():
            raise RuntimeError(f"Output file was not created: {final_output}")

        file_size = final_output.stat().st_size
        print(f"[Pipeline] Output file size: {file_size} bytes")

        if file_size == 0:
            raise RuntimeError("Output file is empty")

        # Clean up temp files
        if os.path.exists(audio_path):
            os.unlink(audio_path)
        if os.path.exists(output_path):
            os.unlink(output_path)

        print("\n" + "=" * 50)
        print("PIPELINE COMPLETE!")
        print(f"[Pipeline] Serving file from: {final_output}")
        print("=" * 50)

        # Read the entire file and return as response
        # This is more reliable for video playback in browsers
        with open(final_output, "rb") as f:
            video_bytes = f.read()

        file_size = len(video_bytes)
        print(f"[Pipeline] Returning {file_size} bytes to client")

        return Response(
            content=video_bytes,
            media_type="video/mp4",
            headers={
                "Content-Disposition": f'inline; filename="with_audio_{safe_filename}.mp4"',
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Pipeline] CRITICAL ERROR: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # Clean up uploaded temp file
        if temp_video_path and os.path.exists(temp_video_path):
            os.unlink(temp_video_path)


@app.post("/api/analyze-only")
@limiter.limit("5/hour")
async def analyze_only(request: Request, video: UploadFile = File(...)):
    """Debug endpoint: Only run GCP analysis and return the context."""
    suffix = Path(video.filename).suffix if video.filename else ".mp4"
    temp_video = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    content = await video.read()
    temp_video.write(content)
    temp_video.close()

    try:
        context = await analyze_video(temp_video.name)
        duration = get_video_duration(temp_video.name)
        print("\n[Debug] === GCP VIDEO CONTEXT ===")
        print(context)
        print("===============================\n")
        return {"context": context, "duration": duration}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.unlink(temp_video.name)


@app.post("/api/prompt-only")
@limiter.limit("5/hour")
async def prompt_only(request: Request, video: UploadFile = File(...)):
    """Debug endpoint: Run GCP analysis + OpenAI prompt generation."""
    suffix = Path(video.filename).suffix if video.filename else ".mp4"
    temp_video = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    content = await video.read()
    temp_video.write(content)
    temp_video.close()

    try:
        context = await analyze_video(temp_video.name)
        duration = get_video_duration(temp_video.name)
        prompt_result = await generate_suno_prompt(context, duration)

        print("\n[Debug] === OPENAI PROMPT ===")
        print(prompt_result['prompt'])
        print(f"Tags: {prompt_result['tags']}")
        print("=============================\n")

        return {
            "context": context,
            "duration": duration,
            "suno_prompt": prompt_result["prompt"],
            "tags": prompt_result["tags"],
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.unlink(temp_video.name)


@app.get("/api/outputs/{filename}")
async def get_output_file(filename: str):
    """Debug endpoint: Serve a file from the outputs directory."""
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    # Read and return the file
    with open(file_path, "rb") as f:
        video_bytes = f.read()

    return Response(
        content=video_bytes,
        media_type="video/mp4",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Content-Length": str(len(video_bytes)),
            "Accept-Ranges": "bytes",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
