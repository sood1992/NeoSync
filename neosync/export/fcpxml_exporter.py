"""
Final Cut Pro XML Exporter
==========================

Export synchronized clips to FCPXML format for Final Cut Pro X/11.
Supports FCPXML version 1.9+
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path
from typing import List, Optional
from datetime import datetime
import os
import re

from ..core.sync_engine import ClipInfo, SyncProject


def sanitize_name(name: str) -> str:
    """Sanitize name for XML"""
    return re.sub(r'[^\w\s\-\.]', '_', name)


def seconds_to_fcptime(seconds: float, fps: float = 24.0) -> str:
    """Convert seconds to FCP time format (frames/fps notation)"""
    frames = int(round(seconds * fps))
    # FCP uses rational time like "86400/24s" (3600 seconds)
    # Simplify the fraction
    from math import gcd
    fps_int = int(fps * 1000)  # Handle fractional fps like 23.976
    frames_scaled = int(frames * 1000)
    g = gcd(frames_scaled, fps_int)
    num = frames_scaled // g
    den = fps_int // g
    return f"{num}/{den}s"


def frames_to_fcptime(frames: int, fps: float = 24.0) -> str:
    """Convert frames to FCP time format"""
    # Use frame count / fps format
    fps_num, fps_den = fps_to_rational(fps)
    time_num = frames * fps_den
    time_den = fps_num
    from math import gcd
    g = gcd(time_num, time_den)
    return f"{time_num // g}/{time_den // g}s"


def fps_to_rational(fps: float) -> tuple:
    """Convert fps to rational number (num, den)"""
    common_fps = {
        23.976: (24000, 1001),
        23.98: (24000, 1001),
        24.0: (24, 1),
        25.0: (25, 1),
        29.97: (30000, 1001),
        30.0: (30, 1),
        50.0: (50, 1),
        59.94: (60000, 1001),
        60.0: (60, 1),
    }
    # Find closest match
    for known_fps, rational in common_fps.items():
        if abs(fps - known_fps) < 0.01:
            return rational
    # Default to simple integer
    return (int(round(fps)), 1)


class FCPXMLExporter:
    """
    Export synchronized clips to FCPXML format

    Compatible with:
    - Final Cut Pro X (10.4+)
    - Final Cut Pro 11
    - DaVinci Resolve (via FCPXML import)
    """

    VERSION = "1.9"  # FCPXML version

    def __init__(self, project: SyncProject):
        self.project = project
        self.clips = project.clips
        self.fps = 24.0  # Will be determined from clips

        # Determine project fps from reference clip
        if project.reference_clip and project.reference_clip.metadata:
            self.fps = project.reference_clip.metadata.fps

    def export(self, output_path: str, include_audio: bool = True) -> str:
        """
        Export to FCPXML file

        Args:
            output_path: Path to save XML file
            include_audio: Include audio tracks

        Returns:
            Path to created file
        """
        # Create root element
        root = ET.Element('fcpxml', version=self.VERSION)

        # Add resources
        resources = ET.SubElement(root, 'resources')
        self._add_format_resource(resources)
        self._add_media_resources(resources)

        # Add library and event
        library = ET.SubElement(root, 'library')
        event = ET.SubElement(library, 'event', name=sanitize_name(self.project.name))

        # Add project with timeline
        project = ET.SubElement(event, 'project', name=sanitize_name(self.project.name))
        sequence = ET.SubElement(project, 'sequence',
                                  format="r1",
                                  tcStart="0s",
                                  tcFormat="NDF")

        # Add spine (main timeline)
        spine = ET.SubElement(sequence, 'spine')
        self._add_clips_to_spine(spine, include_audio)

        # Format and save
        xml_str = self._prettify(root)

        output_path = str(Path(output_path))
        if not output_path.endswith('.fcpxml'):
            output_path += '.fcpxml'

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(xml_str)

        return output_path

    def _add_format_resource(self, resources: ET.Element):
        """Add format resource for timeline"""
        fps_num, fps_den = fps_to_rational(self.fps)

        # Get resolution from first clip
        width, height = 1920, 1080
        for clip in self.clips:
            if clip.metadata:
                width = clip.metadata.width or 1920
                height = clip.metadata.height or 1080
                break

        ET.SubElement(resources, 'format',
                      id="r1",
                      name=f"{width}x{height} {self.fps}fps",
                      frameDuration=f"{fps_den}/{fps_num}s",
                      width=str(width),
                      height=str(height))

    def _add_media_resources(self, resources: ET.Element):
        """Add media asset resources"""
        for i, clip in enumerate(self.clips):
            asset_id = f"r{i + 10}"  # Start at r10 to avoid conflict with format

            # Calculate duration
            if clip.metadata:
                duration = seconds_to_fcptime(clip.metadata.duration_seconds, self.fps)
                has_audio = "1" if clip.has_audio else "0"
                has_video = "1"
            else:
                duration = "0s"
                has_audio = "0"
                has_video = "1"

            asset = ET.SubElement(resources, 'asset',
                                   id=asset_id,
                                   name=sanitize_name(clip.file_name),
                                   src=f"file://{clip.file_path}",
                                   start="0s",
                                   duration=duration,
                                   hasVideo=has_video,
                                   hasAudio=has_audio,
                                   format="r1")

            # Store asset ID for later reference
            clip._asset_id = asset_id

    def _add_clips_to_spine(self, spine: ET.Element, include_audio: bool):
        """Add synchronized clips to spine"""
        # Sort clips by sync offset
        sorted_clips = sorted(self.clips, key=lambda c: c.sync_offset_seconds)

        # Find the earliest offset to normalize timeline
        min_offset = min(c.sync_offset_seconds for c in sorted_clips) if sorted_clips else 0

        # Track current position
        current_pos = 0.0

        for clip in sorted_clips:
            clip_start = clip.sync_offset_seconds - min_offset
            duration = clip.duration if clip.duration > 0 else 10.0

            # Add gap if needed
            gap = clip_start - current_pos
            if gap > 0.01:  # More than 1 frame
                gap_elem = ET.SubElement(spine, 'gap',
                                          offset=seconds_to_fcptime(current_pos, self.fps),
                                          duration=seconds_to_fcptime(gap, self.fps))
                current_pos = clip_start

            # Add asset-clip
            asset_clip = ET.SubElement(spine, 'asset-clip',
                                        ref=clip._asset_id,
                                        offset=seconds_to_fcptime(current_pos, self.fps),
                                        name=sanitize_name(clip.file_name),
                                        duration=seconds_to_fcptime(duration, self.fps),
                                        format="r1",
                                        tcFormat="NDF")

            # Add audio configuration if needed
            if include_audio and clip.has_audio:
                audio_elem = ET.SubElement(asset_clip, 'audio-channel-source',
                                           srcCh="1, 2",
                                           outCh="L, R")

            # Add marker with sync info
            marker = ET.SubElement(asset_clip, 'marker',
                                    start="0s",
                                    duration="1/24s",
                                    value=f"Confidence: {clip.sync_confidence:.1%}")
            marker.text = f"Synced: {clip.sync_method.value if clip.sync_method else 'N/A'}"

            current_pos += duration

    def _prettify(self, elem: ET.Element) -> str:
        """Return a pretty-printed XML string"""
        rough_string = ET.tostring(elem, encoding='unicode')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")

    def export_multicam(self, output_path: str) -> str:
        """
        Export as multicam clip in FCPXML

        Creates a synchronized multicam clip with all cameras
        """
        root = ET.Element('fcpxml', version=self.VERSION)
        resources = ET.SubElement(root, 'resources')

        self._add_format_resource(resources)
        self._add_media_resources(resources)

        # Create multicam resource
        mc_id = "r_multicam"

        # Find timeline duration
        sorted_clips = sorted(self.clips, key=lambda c: c.sync_offset_seconds)
        min_offset = min(c.sync_offset_seconds for c in sorted_clips)
        max_end = max(c.sync_offset_seconds + c.duration for c in sorted_clips)
        total_duration = max_end - min_offset

        mc_clip = ET.SubElement(resources, 'mc-clip',
                                 id=mc_id,
                                 name=f"{self.project.name}_Multicam",
                                 tcStart="0s",
                                 tcFormat="NDF")

        # Add angles (one per camera)
        cameras = {}
        for clip in self.clips:
            cam_id = clip.camera_id or "Unknown"
            if cam_id not in cameras:
                cameras[cam_id] = []
            cameras[cam_id].append(clip)

        for i, (cam_name, cam_clips) in enumerate(cameras.items()):
            angle = ET.SubElement(mc_clip, 'mc-angle',
                                   name=sanitize_name(cam_name),
                                   angleID=str(i + 1))

            for clip in cam_clips:
                clip_offset = clip.sync_offset_seconds - min_offset
                asset_clip = ET.SubElement(angle, 'asset-clip',
                                            ref=clip._asset_id,
                                            offset=seconds_to_fcptime(clip_offset, self.fps),
                                            name=sanitize_name(clip.file_name),
                                            duration=seconds_to_fcptime(clip.duration, self.fps))

        # Add library and event
        library = ET.SubElement(root, 'library')
        event = ET.SubElement(library, 'event', name=sanitize_name(self.project.name))

        # Reference the multicam clip
        ref_clip = ET.SubElement(event, 'ref-clip',
                                  ref=mc_id,
                                  name=f"{self.project.name}_Multicam",
                                  duration=seconds_to_fcptime(total_duration, self.fps))

        xml_str = self._prettify(root)

        output_path = str(Path(output_path))
        if not output_path.endswith('.fcpxml'):
            output_path += '.fcpxml'

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(xml_str)

        return output_path
