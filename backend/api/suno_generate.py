"""
Suno AI music generation integration (Official TreeHacks API).
Takes a detailed prompt and generates audio using the Suno API.

Docs: https://studio-api.prod.suno.com/api/v2/external/hackathons/docs
"""

import os
import time
import httpx
import asyncio
import tempfile

# Use the official TreeHacks API endpoint
SUNO_API_URL = "https://studio-api.prod.suno.com/api/v2/external/hackathons"
SUNO_API_KEY = os.getenv("SUNO_API_KEY", "")

POLL_INTERVAL = 5  # seconds between status checks
MAX_WAIT_TIME = 300  # max seconds to wait for generation


async def generate_audio(prompt: str, tags: str = "", duration: float = None, negative_tags: str = None) -> str:
    """
    Generate audio using Suno API (Official TreeHacks Endpoint).

    Args:
        prompt: The structured music prompt (lyrics/metatags with duration emphasized).
        tags: Comma-separated style tags (e.g. "cinematic, orchestral, emotional").
        duration: Video duration in seconds (used for title only, NOT an API parameter).
        negative_tags: Optional comma-separated tags to avoid (e.g. "harsh, aggressive, distorted").

    Returns:
        Path to the downloaded audio file.

    Note: Suno's API does NOT have a duration parameter. Duration must be emphasized
    multiple times in the prompt text itself for best results.
    """
    if not SUNO_API_KEY:
        raise ValueError("SUNO_API_KEY is missing in .env file")

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Step 1: Submit generation request
        print("[Suno] Submitting audio generation request...")
        print(f"[Suno] Tags: {tags}")
        if negative_tags:
            print(f"[Suno] Negative tags: {negative_tags}")

        # Official API Payload for Custom Mode
        # We use 'prompt' for the structure/lyrics and 'tags' for style
        title = "Bruno AI Generation"
        if duration:
            title = f"Bruno AI Generation ({duration:.0f}s)"

        payload = {
            "prompt": prompt,
            "tags": tags,
            "make_instrumental": False,  # Allow vocals with lyrics
            "title": title
        }

        # Add negative_tags if provided
        if negative_tags:
            payload["negative_tags"] = negative_tags

        headers = {
            "Authorization": f"Bearer {SUNO_API_KEY}",
            "Content-Type": "application/json"
        }

        try:
            response = await client.post(
                f"{SUNO_API_URL}/generate",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            print(f"[Suno] API Error: {e.response.text}")
            raise RuntimeError(f"Suno API failed with status {e.response.status_code}")
        except httpx.HTTPError as e:
            raise RuntimeError(f"Failed to connect to Suno API: {e}")

        result = response.json()
        
        # The official API returns a single clip object directly
        # Example: { "id": "...", "status": "submitted", ... }
        if not result or "id" not in result:
             raise ValueError(f"Unexpected Suno API response format: {result}")

        gen_id = result["id"]
        print(f"[Suno] Generation started with ID: {gen_id}")

        # Step 2: Poll for completion
        audio_url = await _poll_for_completion(client, gen_id, headers)

        # Step 3: Download the audio file
        output_path = await _download_audio(client, audio_url)

        print(f"[Suno] Audio saved to: {output_path}")
        return output_path


async def _poll_for_completion(client: httpx.AsyncClient, gen_id: str, headers: dict) -> str:
    """Poll the Suno API until audio generation is complete."""
    elapsed = 0

    while elapsed < MAX_WAIT_TIME:
        print(f"[Suno] Checking status... ({elapsed}s elapsed)")

        try:
            # Official API: GET /clips?ids=...
            response = await client.get(
                f"{SUNO_API_URL}/clips",
                params={"ids": gen_id},
                headers=headers,
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            print(f"[Suno] Warning: Status check failed ({e}), retrying...")
            await asyncio.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL
            continue

        result = response.json()

        # Response is a list of clips: [ { "id": "...", "status": "...", ... } ]
        if isinstance(result, list) and len(result) > 0:
            status_obj = result[0]
        else:
            # Wait a bit if the clip isn't found yet (event consistency)
            await asyncio.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL
            continue

        status = status_obj.get("status", "")
        audio_url = status_obj.get("audio_url", "")

        # "streaming" means we can start playing, "complete" means it's done.
        # For this pipeline, we probably want to wait for "complete" to get the full file for merging.
        # If you want to stream, you can return early here.
        if status == "complete" and audio_url:
            print("[Suno] Generation complete!")
            return audio_url
        elif status == "error":
            error_msg = status_obj.get("metadata", {}).get("error_message", "Unknown error")
            raise RuntimeError(f"Suno generation failed: {error_msg}")

        await asyncio.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

    raise TimeoutError(f"Suno generation timed out after {MAX_WAIT_TIME}s")


async def _download_audio(client: httpx.AsyncClient, audio_url: str) -> str:
    """Download the generated audio file to a temp location."""
    print(f"[Suno] Downloading audio from: {audio_url}")

    try:
        response = await client.get(audio_url)
        response.raise_for_status()
    except httpx.HTTPError as e:
        raise RuntimeError(f"Failed to download audio from {audio_url}: {e}")

    # Save to temp file
    suffix = ".mp3"
    if "wav" in audio_url:
        suffix = ".wav"
    elif "mp4" in audio_url:
        suffix = ".mp4"

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="suno_")
    temp_file.write(response.content)
    temp_file.close()

    return temp_file.name
