"""
Media combination module.
Takes an audioless video and a generated audio file, and merges them into a single video with audio.
Uses moviepy for the combination.
"""

import os
import tempfile
from moviepy.editor import VideoFileClip, AudioFileClip


async def combine_video_audio(video_path: str, audio_path: str) -> str:
    """
    Combine an audioless video with a generated audio track.
    
    Args:
        video_path: Path to the original audioless video file.
        audio_path: Path to the generated audio file (mp3/wav).
    
    Returns:
        Path to the output video file with audio.
    """
    video_clip = None
    audio_clip = None
    final_clip = None
    
    try:
        print(f"[Combine] Loading video: {video_path}")
        print(f"[Combine] Loading audio: {audio_path}")

        try:
            video_clip = VideoFileClip(video_path)
            audio_clip = AudioFileClip(audio_path)
        except Exception as e:
            raise RuntimeError(f"Failed to load media files: {e}")

        # Trim audio to match video duration if audio is longer
        if audio_clip.duration > video_clip.duration:
            print(f"[Combine] Trimming audio from {audio_clip.duration:.1f}s to {video_clip.duration:.1f}s")
            audio_clip = audio_clip.subclip(0, video_clip.duration)
        
        # If audio is shorter than video, it will just stop (video continues silent)
        if audio_clip.duration < video_clip.duration:
            print(f"[Combine] Note: Audio ({audio_clip.duration:.1f}s) is shorter than video ({video_clip.duration:.1f}s)")

        # Set the audio on the video
        final_clip = video_clip.set_audio(audio_clip)

        # Generate output path
        output_path = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".mp4",
            prefix="output_",
        ).name

        print(f"[Combine] Writing final video to: {output_path}")
        try:
            final_clip.write_videofile(
                output_path,
                codec="libx264",
                audio_codec="aac",
                temp_audiofile=tempfile.mktemp(suffix=".m4a"),
                remove_temp=True,
                logger=None,  # Suppress moviepy's verbose output
            )
        except Exception as e:
            raise RuntimeError(f"Failed to write final video file: {e}")

        print(f"[Combine] Done! Output: {output_path}")
        return output_path
        
    except Exception as e:
        print(f"[Combine] Error: {e}")
        raise
        
    finally:
        # Clean up resources
        if video_clip:
            try: video_clip.close()
            except: pass
        if audio_clip:
            try: audio_clip.close()
            except: pass
        if final_clip:
            try: final_clip.close()
            except: pass


def get_video_duration(video_path: str) -> float:
    """Get the duration of a video file in seconds."""
    try:
        clip = VideoFileClip(video_path)
        duration = clip.duration
        clip.close()
        return duration
    except Exception as e:
        print(f"[Combine] Error getting duration: {e}")
        # Return a fallback or re-raise depending on strictness. 
        # Re-raising is safer as we need duration for logic.
        raise RuntimeError(f"Could not determine video duration: {e}")
