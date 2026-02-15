"""
OpenAI integration - Generates Suno-optimized music prompts with planned lyrics.
Strict genre-authentic, scene-grounded, duration-controlled generation.
"""

import os
from openai import AsyncOpenAI, APIError


SYSTEM_PROMPT = """
You are a professional Suno AI music director.

Your task is to generate a tightly structured Suno prompt that includes:
1) Scene-grounded lyrics
2) A clear, production-ready music structure
3) Precise timing control

==================================================
CORE OBJECTIVE
==================================================

The song must feel like a REAL, AVERAGE, commercially released track
from the chosen genre.

The lyrics must:
• Match the genre’s writing style
• Match the genre’s phrasing patterns
• Match the genre’s structure simplicity
• Feel natural for that genre

The lyrics must describe what is happening in the VIDEO.

==================================================
CRITICAL LYRIC RULES
==================================================

The lyrics MUST describe:
• Actions
• Physical environments
• Observable moments
• Movement
• Specific imagery

Do NOT:
• Repeat emotional labels from the input
• Convert adjectives from the analysis into lyrics
• Write abstract “vibe” poetry
• Reference music, sound, rhythm, instruments
• Use generic inspirational filler
• Over-philosophize

Translate tone into genre-appropriate phrasing,
but keep lyrics grounded in visible actions and detail.

==================================================
GENRE AUTHENTICITY REQUIREMENT
==================================================

Before writing lyrics, internally determine:

• What genre best fits the video?
• How do average songs in that genre phrase lines?
• Are they direct? Conversational? Minimal?
• How simple are their hooks?

Then write lyrics that mirror:
• Sentence length
• Simplicity level
• Repetition style
• Cadence feel

The result should feel like a believable mainstream track
from that genre — not experimental poetry.

Keep phrasing natural.
Keep language accessible.
Avoid metaphor stacking.

==================================================
LYRICS CONSTRAINTS
==================================================

• 2–4 SHORT lines per lyrical section
• Strong verbs
• Concrete nouns
• Natural spoken rhythm
• Simple, repeatable chorus lines (if used)

No filler.
No dramatic over-writing.
No excessive adjectives.

==================================================
MUSIC STRUCTURE RULES
==================================================

Always follow this exact structure:

[Section Name]
Primary Genre, Mood, Key Instrument, Vocal Type, BPM

[Section – X to Y seconds]
Genre + 2-3 specific instruments + vocal type + production tone + BPM

Constraints:
• 4–7 descriptors max
• Primary genre FIRST
• Always include BPM
• BPM must stay consistent
• Always specify vocal type OR “pure instrumental, no vocals”
• No production rambling

==================================================
DURATION CONTROL (MANDATORY)
==================================================

The track MUST end exactly at the specified duration.

You MUST:
• Mention the exact duration at least 4 times
• Map timestamps precisely
• In Outro include:
    "Fade begins at X seconds"
    "Vocals fade at X+2 seconds"
    "Complete silence by END seconds"
    "ENDS AT END SECONDS"

Final line MUST be:

TOTAL TRACK LENGTH: END SECONDS. HARD STOP AT END SECONDS.

If duration is 17.4 seconds, write 17.4 seconds — not rounded.

No commentary after that line.

==================================================
FINAL INTERNAL CHECK
==================================================

Before outputting, verify:

✔ Lyrics describe visible actions or physical details
✔ No emotional labels copied
✔ No music references in lyrics
✔ Feels like an average real song from the chosen genre
✔ BPM consistent
✔ Genre listed first
✔ Duration referenced at least 4 times
✔ No extra explanation outside required format

Output ONLY the formatted Suno prompt.
No commentary.
No explanation.
No extra text.
"""


async def generate_suno_prompt(video_context: str, video_duration: float = None) -> dict:
    """
    Generate Suno-optimized music prompt with planned lyrics based on video content.

    Args:
        video_context: Video analysis from GCP with scenes, labels, and timestamps.
        video_duration: Exact video duration in seconds (REQUIRED).

    Returns:
        Dict with:
        - 'prompt': Full Suno prompt with lyrics + structure + timing
        - 'tags': Short comma-separated style keywords
        - 'negative_tags': Anti-style tags to avoid mismatches
    """

    try:
        if not video_duration:
            raise ValueError("video_duration is REQUIRED to generate accurate music timing")

        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Section timing logic
        intro_end = min(video_duration * 0.25, 8)
        verse_end = min(video_duration * 0.75, video_duration - 3)
        outro_start = verse_end

        user_message = f"""
VIDEO DURATION: {video_duration:.2f} seconds
TRACK MUST END EXACTLY AT {video_duration:.2f} seconds

VIDEO ANALYSIS:
{video_context}

INSTRUCTIONS:

1. Choose a genre that realistically matches the video.
2. Write lyrics about visible actions and environments only.
3. Do NOT reuse emotional adjectives from the analysis.
4. Follow strict duration mapping:
   - Intro: 0 to ~{intro_end:.2f} seconds
   - Verse: ~{intro_end:.2f} to ~{verse_end:.2f} seconds
   - Outro: ~{outro_start:.2f} to {video_duration:.2f} seconds
5. Duration must be stated at least 4 times.
6. Final line must be:
   TOTAL TRACK LENGTH: {video_duration:.2f} SECONDS. HARD STOP AT {video_duration:.2f} SECONDS.
"""

        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.75,
            max_tokens=800,
        )

        suno_prompt = response.choices[0].message.content.strip()

        # Extract tags
        lines = suno_prompt.split("\n")
        tags = "Cinematic, 100 BPM"

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("["):
                for j in range(i + 1, min(i + 3, len(lines))):
                    candidate = lines[j].strip()
                    if candidate and "," in candidate and len(candidate) < 120:
                        tags = candidate
                        break
                break

        negative_tags = await _generate_negative_tags(client, video_context, tags)

        return {
            "prompt": suno_prompt,
            "tags": tags,
            "negative_tags": negative_tags,
        }

    except APIError as e:
        raise RuntimeError(f"OpenAI API failed: {e}")
    except Exception as e:
        raise


async def _generate_negative_tags(client: AsyncOpenAI, video_context: str, positive_tags: str) -> str:
    """
    Generate negative tags (anti-tags) to avoid unwanted styles in Suno generation.
    """

    try:
        negative_prompt = f"""
Suggest 3-5 NEGATIVE music style tags that would clash with:

VIDEO CONTEXT:
{video_context}

POSITIVE TAGS:
{positive_tags}

Return ONLY a comma-separated list of 3-5 negative tags.
No explanation.
"""

        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": negative_prompt}],
            temperature=0.4,
            max_tokens=50,
        )

        return response.choices[0].message.content.strip()

    except Exception:
        return "harsh, distorted, chaotic, muddy, robotic"
