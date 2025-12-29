"""
Adobe Premiere Pro XML Exporter
===============================

Export synchronized clips to Premiere Pro XML format.
Compatible with Premiere Pro CC 2019+
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path
from typing import List, Optional
from datetime import datetime
import os
import re
import uuid

from ..core.sync_engine import ClipInfo, SyncProject


def sanitize_name(name: str) -> str:
    """Sanitize name for XML"""
    return re.sub(r'[^\w\s\-\.]', '_', name)


def seconds_to_ticks(seconds: float, timebase: int = 24) -> int:
    """Convert seconds to Premiere ticks (90000 ticks per second base)"""
    return int(seconds * 254016000000)  # Premiere's tick rate


def frames_to_ticks(frames: int, fps: float) -> int:
    """Convert frames to ticks"""
    seconds = frames / fps
    return seconds_to_ticks(seconds)


class PremiereXMLExporter:
    """
    Export synchronized clips to Premiere Pro XML

    Compatible with:
    - Adobe Premiere Pro CC 2019+
    - Adobe Premiere Pro 2024
    - After Effects (via import)
    """

    def __init__(self, project: SyncProject):
        self.project = project
        self.clips = project.clips
        self.fps = 24.0
        self.timebase = 24

        # Determine project fps from reference clip
        if project.reference_clip and project.reference_clip.metadata:
            self.fps = project.reference_clip.metadata.fps
            self.timebase = int(round(self.fps))

    def _generate_uuid(self) -> str:
        """Generate UUID for Premiere elements"""
        return str(uuid.uuid4())

    def export(self, output_path: str, include_audio: bool = True) -> str:
        """
        Export to Premiere Pro XML file

        Args:
            output_path: Path to save XML file
            include_audio: Include audio tracks

        Returns:
            Path to created file
        """
        # Create root element
        root = ET.Element('xmeml', version="5")

        # Add project
        project = ET.SubElement(root, 'project')
        ET.SubElement(project, 'name').text = sanitize_name(self.project.name)

        # Add children (bins, sequences)
        children = ET.SubElement(project, 'children')

        # Add bin for source clips
        bin_elem = ET.SubElement(children, 'bin')
        ET.SubElement(bin_elem, 'name').text = "Source Clips"
        bin_children = ET.SubElement(bin_elem, 'children')

        # Add clip items to bin
        clip_ids = {}
        for i, clip in enumerate(self.clips):
            clip_id = f"masterclip-{i+1}"
            clip_ids[clip.id] = clip_id
            self._add_clip_item(bin_children, clip, clip_id)

        # Add sequence
        sequence = self._create_sequence(children, clip_ids, include_audio)

        # Format and save
        xml_str = self._prettify(root)

        output_path = str(Path(output_path))
        if not output_path.endswith('.xml'):
            output_path += '.xml'

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(xml_str)

        return output_path

    def _add_clip_item(self, parent: ET.Element, clip: ClipInfo, clip_id: str):
        """Add a clip item to the bin"""
        clip_elem = ET.SubElement(parent, 'clip', id=clip_id)
        ET.SubElement(clip_elem, 'uuid').text = self._generate_uuid()
        ET.SubElement(clip_elem, 'masterclipid').text = clip_id
        ET.SubElement(clip_elem, 'name').text = sanitize_name(clip.file_name)

        # Duration
        duration_frames = int(clip.duration * self.fps) if clip.duration > 0 else 1
        ET.SubElement(clip_elem, 'duration').text = str(duration_frames)

        # Rate
        rate = ET.SubElement(clip_elem, 'rate')
        ET.SubElement(rate, 'timebase').text = str(self.timebase)
        ET.SubElement(rate, 'ntsc').text = "FALSE" if self.fps == int(self.fps) else "TRUE"

        # In/Out points
        ET.SubElement(clip_elem, 'in').text = "0"
        ET.SubElement(clip_elem, 'out').text = str(duration_frames)

        # Media
        media = ET.SubElement(clip_elem, 'media')

        # Video
        if clip.metadata:
            video = ET.SubElement(media, 'video')
            track = ET.SubElement(video, 'track')
            clip_item = ET.SubElement(track, 'clipitem', id=f"{clip_id}-video")

            ET.SubElement(clip_item, 'name').text = sanitize_name(clip.file_name)
            ET.SubElement(clip_item, 'duration').text = str(duration_frames)

            # Rate for clip item
            rate2 = ET.SubElement(clip_item, 'rate')
            ET.SubElement(rate2, 'timebase').text = str(self.timebase)

            ET.SubElement(clip_item, 'in').text = "0"
            ET.SubElement(clip_item, 'out').text = str(duration_frames)
            ET.SubElement(clip_item, 'start').text = "0"
            ET.SubElement(clip_item, 'end').text = str(duration_frames)

            # File reference
            file_elem = ET.SubElement(clip_item, 'file', id=f"file-{clip.id}")
            ET.SubElement(file_elem, 'name').text = sanitize_name(clip.file_name)
            ET.SubElement(file_elem, 'pathurl').text = f"file://localhost{clip.file_path}"
            ET.SubElement(file_elem, 'duration').text = str(duration_frames)

            # File rate
            file_rate = ET.SubElement(file_elem, 'rate')
            ET.SubElement(file_rate, 'timebase').text = str(self.timebase)

            # Media info
            file_media = ET.SubElement(file_elem, 'media')
            file_video = ET.SubElement(file_media, 'video')
            ET.SubElement(file_video, 'duration').text = str(duration_frames)

            sample_char = ET.SubElement(file_video, 'samplecharacteristics')
            ET.SubElement(sample_char, 'width').text = str(clip.metadata.width or 1920)
            ET.SubElement(sample_char, 'height').text = str(clip.metadata.height or 1080)

        # Audio
        if clip.has_audio:
            audio = ET.SubElement(media, 'audio')
            audio_track = ET.SubElement(audio, 'track')
            audio_item = ET.SubElement(audio_track, 'clipitem', id=f"{clip_id}-audio")

            ET.SubElement(audio_item, 'name').text = sanitize_name(clip.file_name)
            ET.SubElement(audio_item, 'duration').text = str(duration_frames)

            # Audio file reference
            audio_file = ET.SubElement(audio_item, 'file', id=f"file-audio-{clip.id}")
            ET.SubElement(audio_file, 'name').text = sanitize_name(clip.file_name)
            ET.SubElement(audio_file, 'pathurl').text = f"file://localhost{clip.file_path}"

    def _create_sequence(
        self,
        parent: ET.Element,
        clip_ids: dict,
        include_audio: bool
    ) -> ET.Element:
        """Create the synchronized sequence"""
        sequence = ET.SubElement(parent, 'sequence', id="sequence-1")
        ET.SubElement(sequence, 'uuid').text = self._generate_uuid()
        ET.SubElement(sequence, 'name').text = f"{self.project.name} - Synced"

        # Calculate duration
        sorted_clips = sorted(self.clips, key=lambda c: c.sync_offset_seconds)
        min_offset = min(c.sync_offset_seconds for c in sorted_clips)
        max_end = max(c.sync_offset_seconds + c.duration for c in sorted_clips)
        total_duration = max_end - min_offset
        duration_frames = int(total_duration * self.fps)

        ET.SubElement(sequence, 'duration').text = str(duration_frames)

        # Rate
        rate = ET.SubElement(sequence, 'rate')
        ET.SubElement(rate, 'timebase').text = str(self.timebase)
        ET.SubElement(rate, 'ntsc').text = "FALSE" if self.fps == int(self.fps) else "TRUE"

        # Timecode
        timecode = ET.SubElement(sequence, 'timecode')
        tc_rate = ET.SubElement(timecode, 'rate')
        ET.SubElement(tc_rate, 'timebase').text = str(self.timebase)
        ET.SubElement(timecode, 'string').text = "00:00:00:00"
        ET.SubElement(timecode, 'frame').text = "0"
        ET.SubElement(timecode, 'displayformat').text = "NDF"

        # Media
        media = ET.SubElement(sequence, 'media')

        # Video tracks - group by camera
        video = ET.SubElement(media, 'video')
        format_elem = ET.SubElement(video, 'format')
        sample_char = ET.SubElement(format_elem, 'samplecharacteristics')
        ET.SubElement(sample_char, 'width').text = "1920"
        ET.SubElement(sample_char, 'height').text = "1080"

        # Group clips by camera
        cameras = {}
        for clip in self.clips:
            cam_id = clip.camera_id or "Unknown"
            if cam_id not in cameras:
                cameras[cam_id] = []
            cameras[cam_id].append(clip)

        # Create a track per camera
        for track_idx, (cam_name, cam_clips) in enumerate(cameras.items()):
            track = ET.SubElement(video, 'track')
            ET.SubElement(track, 'enabled').text = "TRUE"
            ET.SubElement(track, 'locked').text = "FALSE"

            for clip in cam_clips:
                clip_offset = clip.sync_offset_seconds - min_offset
                start_frame = int(clip_offset * self.fps)
                duration = clip.duration if clip.duration > 0 else 10
                end_frame = start_frame + int(duration * self.fps)

                clip_item = ET.SubElement(track, 'clipitem', id=f"seq-clip-{clip.id}")
                ET.SubElement(clip_item, 'masterclipid').text = clip_ids.get(clip.id, "")
                ET.SubElement(clip_item, 'name').text = sanitize_name(clip.file_name)

                ET.SubElement(clip_item, 'duration').text = str(int(duration * self.fps))
                ET.SubElement(clip_item, 'in').text = "0"
                ET.SubElement(clip_item, 'out').text = str(int(duration * self.fps))
                ET.SubElement(clip_item, 'start').text = str(start_frame)
                ET.SubElement(clip_item, 'end').text = str(end_frame)

                # Rate
                item_rate = ET.SubElement(clip_item, 'rate')
                ET.SubElement(item_rate, 'timebase').text = str(self.timebase)

                # File reference
                file_elem = ET.SubElement(clip_item, 'file', id=f"seq-file-{clip.id}")
                ET.SubElement(file_elem, 'pathurl').text = f"file://localhost{clip.file_path}"

                # Add label color based on sync quality
                labels = ET.SubElement(clip_item, 'labels')
                label_color = self._get_premiere_label_color(clip)
                ET.SubElement(labels, 'label2').text = label_color

        # Audio tracks
        if include_audio:
            audio = ET.SubElement(media, 'audio')

            # Audio format
            audio_format = ET.SubElement(audio, 'format')
            audio_sample = ET.SubElement(audio_format, 'samplecharacteristics')
            ET.SubElement(audio_sample, 'depth').text = "16"
            ET.SubElement(audio_sample, 'samplerate').text = "48000"

            for track_idx, (cam_name, cam_clips) in enumerate(cameras.items()):
                audio_track = ET.SubElement(audio, 'track')
                ET.SubElement(audio_track, 'outputchannelindex').text = str(track_idx + 1)

                for clip in cam_clips:
                    if not clip.has_audio:
                        continue

                    clip_offset = clip.sync_offset_seconds - min_offset
                    start_frame = int(clip_offset * self.fps)
                    duration = clip.duration if clip.duration > 0 else 10
                    end_frame = start_frame + int(duration * self.fps)

                    audio_item = ET.SubElement(audio_track, 'clipitem', id=f"seq-audio-{clip.id}")
                    ET.SubElement(audio_item, 'masterclipid').text = clip_ids.get(clip.id, "")
                    ET.SubElement(audio_item, 'name').text = sanitize_name(clip.file_name)

                    ET.SubElement(audio_item, 'duration').text = str(int(duration * self.fps))
                    ET.SubElement(audio_item, 'in').text = "0"
                    ET.SubElement(audio_item, 'out').text = str(int(duration * self.fps))
                    ET.SubElement(audio_item, 'start').text = str(start_frame)
                    ET.SubElement(audio_item, 'end').text = str(end_frame)

        return sequence

    def _get_premiere_label_color(self, clip: ClipInfo) -> str:
        """Get Premiere label color name based on sync quality"""
        from ..core.sync_engine import SyncQuality

        color_map = {
            SyncQuality.EXCELLENT: "Iris",      # Purple/Blue
            SyncQuality.GOOD: "Caribbean",      # Teal
            SyncQuality.FAIR: "Yellow",         # Yellow
            SyncQuality.POOR: "Orange",         # Orange
            SyncQuality.FAILED: "Rose",         # Red/Pink
        }
        return color_map.get(clip.sync_quality, "Lavender")

    def _prettify(self, elem: ET.Element) -> str:
        """Return a pretty-printed XML string"""
        rough_string = ET.tostring(elem, encoding='unicode')
        # Add XML declaration
        rough_string = '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n' + rough_string
        try:
            reparsed = minidom.parseString(rough_string)
            return reparsed.toprettyxml(indent="  ")
        except:
            return rough_string

    def export_multicam(self, output_path: str) -> str:
        """
        Export as multicam sequence

        Creates a nested multicam sequence with all cameras
        """
        # For Premiere, we create a regular sequence but with tracks arranged for multicam editing
        # Premiere's multicam is created in the program itself from the XML

        return self.export(output_path, include_audio=True)
