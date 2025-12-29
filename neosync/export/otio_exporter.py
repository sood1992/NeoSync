"""
OpenTimelineIO Exporter
=======================

Export synchronized clips to OpenTimelineIO format.
Universal timeline format supported by many NLEs.

https://opentimeline.io/
"""

import os
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..core.sync_engine import ClipInfo, SyncProject, SyncQuality


class OTIOExporter:
    """
    Export synchronized clips to OpenTimelineIO format

    Compatible with:
    - DaVinci Resolve
    - Adobe Premiere Pro (via plugin)
    - Avid Media Composer (via plugin)
    - Final Cut Pro (via plugin)
    - Nuke
    - Hiero
    - And many more!
    """

    SCHEMA_VERSION = "0.12"

    def __init__(self, project: SyncProject):
        self.project = project
        self.clips = project.clips
        self.fps = 24.0

        # Determine project fps from reference clip
        if project.reference_clip and project.reference_clip.metadata:
            self.fps = project.reference_clip.metadata.fps

    def _create_rational_time(self, seconds: float) -> Dict[str, Any]:
        """Create OTIO RationalTime object"""
        return {
            "OTIO_SCHEMA": "RationalTime.1",
            "value": seconds * self.fps,
            "rate": self.fps
        }

    def _create_time_range(self, start_seconds: float, duration_seconds: float) -> Dict[str, Any]:
        """Create OTIO TimeRange object"""
        return {
            "OTIO_SCHEMA": "TimeRange.1",
            "start_time": self._create_rational_time(start_seconds),
            "duration": self._create_rational_time(duration_seconds)
        }

    def _get_color_for_quality(self, quality: SyncQuality) -> str:
        """Get marker color for sync quality"""
        colors = {
            SyncQuality.EXCELLENT: "GREEN",
            SyncQuality.GOOD: "CYAN",
            SyncQuality.FAIR: "YELLOW",
            SyncQuality.POOR: "ORANGE",
            SyncQuality.FAILED: "RED",
        }
        return colors.get(quality, "WHITE")

    def export(self, output_path: str, include_audio: bool = True) -> str:
        """
        Export to OpenTimelineIO file

        Args:
            output_path: Path to save file
            include_audio: Include audio in export

        Returns:
            Path to created file
        """
        # Sort clips and find timeline bounds
        sorted_clips = sorted(self.clips, key=lambda c: c.sync_offset_seconds)
        min_offset = min(c.sync_offset_seconds for c in sorted_clips) if sorted_clips else 0
        max_end = max(c.sync_offset_seconds + c.duration for c in sorted_clips) if sorted_clips else 0

        # Group clips by camera
        cameras: Dict[str, List[ClipInfo]] = {}
        for clip in sorted_clips:
            cam_id = clip.camera_id or "Unknown"
            if cam_id not in cameras:
                cameras[cam_id] = []
            cameras[cam_id].append(clip)

        # Create tracks
        video_tracks = []
        audio_tracks = []

        for cam_name, cam_clips in cameras.items():
            # Video track for this camera
            video_children = []
            audio_children = []
            current_pos = 0.0

            for clip in cam_clips:
                clip_start = clip.sync_offset_seconds - min_offset
                clip_duration = clip.duration if clip.duration > 0 else 10.0

                # Add gap if needed
                gap = clip_start - current_pos
                if gap > 0.01:
                    video_children.append({
                        "OTIO_SCHEMA": "Gap.1",
                        "name": "",
                        "source_range": self._create_time_range(0, gap)
                    })
                    if include_audio and clip.has_audio:
                        audio_children.append({
                            "OTIO_SCHEMA": "Gap.1",
                            "name": "",
                            "source_range": self._create_time_range(0, gap)
                        })
                    current_pos = clip_start

                # Create clip reference
                media_ref = {
                    "OTIO_SCHEMA": "ExternalReference.1",
                    "target_url": f"file://{clip.file_path}",
                    "available_range": self._create_time_range(0, clip_duration),
                    "metadata": {
                        "neosync": {
                            "sync_confidence": clip.sync_confidence,
                            "sync_method": clip.sync_method.value if clip.sync_method else None,
                            "sync_quality": clip.sync_quality.name,
                            "sync_offset": clip.sync_offset_seconds,
                            "camera_id": clip.camera_id
                        }
                    }
                }

                # Create clip
                clip_item = {
                    "OTIO_SCHEMA": "Clip.1",
                    "name": clip.file_name,
                    "source_range": self._create_time_range(0, clip_duration),
                    "media_reference": media_ref,
                    "markers": [
                        {
                            "OTIO_SCHEMA": "Marker.2",
                            "name": f"Sync: {clip.sync_quality.name}",
                            "marked_range": self._create_time_range(0, 0),
                            "color": self._get_color_for_quality(clip.sync_quality),
                            "metadata": {
                                "confidence": f"{clip.sync_confidence:.1%}",
                                "method": clip.sync_method.value if clip.sync_method else "N/A"
                            }
                        }
                    ],
                    "metadata": {
                        "neosync": {
                            "original_file": clip.file_path,
                            "has_audio": clip.has_audio,
                            "duration": clip.duration
                        }
                    }
                }

                video_children.append(clip_item)

                # Add audio clip if needed
                if include_audio and clip.has_audio:
                    audio_clip = {
                        "OTIO_SCHEMA": "Clip.1",
                        "name": f"{clip.file_name} (Audio)",
                        "source_range": self._create_time_range(0, clip_duration),
                        "media_reference": {
                            "OTIO_SCHEMA": "ExternalReference.1",
                            "target_url": f"file://{clip.file_path}",
                            "available_range": self._create_time_range(0, clip_duration)
                        }
                    }
                    audio_children.append(audio_clip)

                current_pos += clip_duration

            # Create video track
            video_track = {
                "OTIO_SCHEMA": "Track.1",
                "name": f"V-{cam_name}",
                "kind": "Video",
                "children": video_children,
                "metadata": {
                    "camera": cam_name
                }
            }
            video_tracks.append(video_track)

            # Create audio track if we have audio clips
            if include_audio and audio_children:
                audio_track = {
                    "OTIO_SCHEMA": "Track.1",
                    "name": f"A-{cam_name}",
                    "kind": "Audio",
                    "children": audio_children,
                    "metadata": {
                        "camera": cam_name
                    }
                }
                audio_tracks.append(audio_track)

        # Create stack
        stack = {
            "OTIO_SCHEMA": "Stack.1",
            "name": "Synced Timeline",
            "children": video_tracks + audio_tracks
        }

        # Create timeline
        timeline = {
            "OTIO_SCHEMA": "Timeline.1",
            "name": f"{self.project.name} - Synced",
            "global_start_time": self._create_rational_time(0),
            "tracks": stack,
            "metadata": {
                "neosync": {
                    "version": "1.0.0",
                    "export_date": datetime.now().isoformat(),
                    "total_clips": len(self.clips),
                    "synced_clips": self.project.total_synced,
                    "failed_clips": self.project.total_failed,
                    "average_confidence": self.project.average_confidence,
                    "fps": self.fps
                }
            }
        }

        # Save to file
        output_path = str(Path(output_path))
        if not output_path.endswith('.otio'):
            output_path += '.otio'

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(timeline, f, indent=2)

        return output_path

    def export_otioz(self, output_path: str, include_media: bool = False) -> str:
        """
        Export to OTIOZ (OpenTimelineIO Zip bundle)

        OTIOZ bundles the .otio file with optional media files.
        """
        import zipfile
        import shutil
        import tempfile

        output_path = str(Path(output_path))
        if not output_path.endswith('.otioz'):
            output_path += '.otioz'

        # Create temp directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Export OTIO
            otio_path = os.path.join(temp_dir, "timeline.otio")
            self.export(otio_path)

            # Create manifest
            manifest = {
                "version": "1.0",
                "content": {
                    "timeline.otio": {
                        "type": "timeline",
                        "schema": "OpenTimelineIO"
                    }
                }
            }

            if include_media:
                manifest["content"]["media"] = {}
                # Copy media files
                media_dir = os.path.join(temp_dir, "media")
                os.makedirs(media_dir, exist_ok=True)

                for clip in self.clips:
                    if os.path.exists(clip.file_path):
                        dest = os.path.join(media_dir, clip.file_name)
                        shutil.copy2(clip.file_path, dest)
                        manifest["content"]["media"][clip.file_name] = {
                            "type": "media",
                            "original_path": clip.file_path
                        }

            manifest_path = os.path.join(temp_dir, "manifest.json")
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)

            # Create zip
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arc_name = os.path.relpath(file_path, temp_dir)
                        zf.write(file_path, arc_name)

        return output_path
