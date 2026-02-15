"""
Google Cloud Video Intelligence API integration.
Takes an audioless video file and returns detailed context/description of what happens.
"""

import os
import json
import time
import uuid
import asyncio
from google.api_core.exceptions import GoogleAPICallError, RetryError

# Lazy imports - will import when function is called
# This prevents import errors if credentials aren't set at startup

# Ensure GOOGLE_APPLICATION_CREDENTIALS env var is set to your service account key JSON path
BUCKET_NAME = "soundscape-ai-uploads-shivam"

async def analyze_video(video_path: str) -> str:
    """
    Analyze a video using Google Cloud Video Intelligence API.
    
    Args:
        video_path: Path to the local video file.
    
    Returns:
        A detailed string description of the video content.
    """
    try:
        # Import here to avoid import errors at module load time
        from google.cloud import videointelligence
        from google.cloud import storage
        
        # 1. Upload to GCS
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        
        # Generate unique filename for GCS
        blob_name = f"uploads/{uuid.uuid4()}_{os.path.basename(video_path)}"
        blob = bucket.blob(blob_name)
        
        print(f"[GCP] Uploading video to gs://{BUCKET_NAME}/{blob_name}...")
        blob.upload_from_filename(video_path)
        gcs_uri = f"gs://{BUCKET_NAME}/{blob_name}"
        print("[GCP] Upload complete.")

        # 2. Analyze using GCS URI
        # Force REST transport to avoid gRPC firewall/hanging issues
        client = videointelligence.VideoIntelligenceServiceClient(transport="rest")

        # Request multiple feature detections for rich context
        features = [
            videointelligence.Feature.LABEL_DETECTION,
            videointelligence.Feature.SHOT_CHANGE_DETECTION,
            videointelligence.Feature.OBJECT_TRACKING,
        ]

        # Configure label detection for shot-level and frame-level granularity
        config = videointelligence.VideoContext(
            label_detection_config=videointelligence.LabelDetectionConfig(
                label_detection_mode=videointelligence.LabelDetectionMode.SHOT_AND_FRAME_MODE
            )
        )

        print(f"[GCP] Starting video analysis on {gcs_uri}...")
        operation = client.annotate_video(
            request={
                "features": features,
                "input_uri": gcs_uri,
                "video_context": config,
            }
        )

        print(f"[GCP] Operation started: {operation.operation.name}")
        print("[GCP] Polling for completion...")

        # Poll for completion manually to show progress/logs
        retry_count = 0
        while not operation.done():
            print(f"[GCP] Still processing... ({retry_count * 5}s elapsed)")
            await asyncio.sleep(5)
            retry_count += 1
            if retry_count > 60: # 5 minutes timeout
                 print("[GCP] Timeout reached! Cancelling operation.")
                 operation.cancel()
                 raise TimeoutError("GCP Video Intelligence operation timed out.")

        print("[GCP] Operation finished!")
        result = operation.result(timeout=10) # Should return immediately since done() is true
        
        # 3. Clean up - Delete from GCS
        print(f"[GCP] Deleting {blob_name} from bucket...")
        try:
            blob.delete()
        except Exception as e:
            print(f"[GCP] Warning: Failed to delete blob {blob_name}: {e}")

        annotation = result.annotation_results[0]

        context_parts = []

        # --- Shot changes ---
        if annotation.shot_annotations:
            context_parts.append("=== SCENE BREAKDOWN ===")
            for i, shot in enumerate(annotation.shot_annotations):
                start = shot.start_time_offset.total_seconds()
                end = shot.end_time_offset.total_seconds()
                context_parts.append(f"Scene {i+1}: {start:.1f}s - {end:.1f}s")

        # --- Labels (what's in the video) ---
        if annotation.shot_label_annotations:
            context_parts.append("\n=== DETECTED LABELS (per scene) ===")
            for label in annotation.shot_label_annotations:
                label_name = label.entity.description
                categories = [c.description for c in label.category_entities]
                cat_str = f" (categories: {', '.join(categories)})" if categories else ""
                segments = []
                for segment in label.segments:
                    start = segment.segment.start_time_offset.total_seconds()
                    end = segment.segment.end_time_offset.total_seconds()
                    confidence = segment.confidence
                    segments.append(f"  {start:.1f}s-{end:.1f}s (confidence: {confidence:.2f})")
                context_parts.append(f"Label: {label_name}{cat_str}")
                context_parts.extend(segments)

        if annotation.frame_label_annotations:
            context_parts.append("\n=== FRAME-LEVEL LABELS ===")
            for label in annotation.frame_label_annotations[:20]:  # Limit to avoid huge outputs
                label_name = label.entity.description
                context_parts.append(f"- {label_name}")

        # --- Object tracking ---
        if annotation.object_annotations:
            context_parts.append("\n=== TRACKED OBJECTS ===")
            seen_objects = {}
            for obj in annotation.object_annotations:
                obj_name = obj.entity.description
                start = obj.segment.start_time_offset.total_seconds()
                end = obj.segment.end_time_offset.total_seconds()
                confidence = obj.confidence
                if obj_name not in seen_objects:
                    seen_objects[obj_name] = []
                seen_objects[obj_name].append(
                    f"  {start:.1f}s-{end:.1f}s (confidence: {confidence:.2f})"
                )
            for obj_name, appearances in seen_objects.items():
                context_parts.append(f"Object: {obj_name}")
                context_parts.extend(appearances[:5])  # Limit appearances shown

        context = "\n".join(context_parts)

        if not context.strip():
            context = "The video analysis returned minimal results. The video may be very short or contain limited visual content."

        print(f"[GCP] Analysis complete. Generated {len(context)} characters of context.")
        return context

    except (GoogleAPICallError, RetryError) as e:
        print(f"[GCP] API Error: {e}")
        raise RuntimeError(f"Google Cloud Video Intelligence API failed: {e}")
    except Exception as e:
        print(f"[GCP] Unexpected error: {e}")
        raise
