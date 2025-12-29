"""
Avid AAF Exporter
=================

Export synchronized clips to AAF (Advanced Authoring Format).
Compatible with Avid Media Composer.

Note: Full AAF requires the pyaaf2 library.
This module provides a fallback that creates an EDL if AAF is not available.
"""

import os
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from ..core.sync_engine import ClipInfo, SyncProject, SyncQuality


def frames_to_timecode(frames: int, fps: float, drop_frame: bool = False) -> str:
    """Convert frame count to timecode string"""
    fps_int = int(round(fps))
    f = frames % fps_int
    total_seconds = frames // fps_int
    s = total_seconds % 60
    total_minutes = total_seconds // 60
    m = total_minutes % 60
    h = total_minutes // 60

    sep = ';' if drop_frame else ':'
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{f:02d}"


def seconds_to_timecode(seconds: float, fps: float, drop_frame: bool = False) -> str:
    """Convert seconds to timecode string"""
    frames = int(round(seconds * fps))
    return frames_to_timecode(frames, fps, drop_frame)


class AAFExporter:
    """
    Export synchronized clips to AAF format

    Compatible with:
    - Avid Media Composer
    - DaVinci Resolve (via AAF import)
    - Pro Tools (audio only)

    Falls back to EDL if pyaaf2 is not installed.
    """

    def __init__(self, project: SyncProject):
        self.project = project
        self.clips = project.clips
        self.fps = 24.0
        self.drop_frame = False

        # Determine project fps from reference clip
        if project.reference_clip and project.reference_clip.metadata:
            self.fps = project.reference_clip.metadata.fps
            # Drop frame for 29.97 and 59.94
            self.drop_frame = self.fps in [29.97, 59.94]

        # Check if pyaaf2 is available
        self.aaf_available = self._check_aaf_available()

    def _check_aaf_available(self) -> bool:
        """Check if pyaaf2 library is available"""
        try:
            import aaf2
            return True
        except ImportError:
            return False

    def export(self, output_path: str, include_audio: bool = True) -> str:
        """
        Export to AAF or EDL file

        Args:
            output_path: Path to save file
            include_audio: Include audio tracks

        Returns:
            Path to created file
        """
        if self.aaf_available:
            return self._export_aaf(output_path, include_audio)
        else:
            # Fall back to EDL
            return self._export_edl(output_path)

    def _export_aaf(self, output_path: str, include_audio: bool) -> str:
        """Export using pyaaf2 library"""
        import aaf2
        from aaf2 import mobs, components

        output_path = str(Path(output_path))
        if not output_path.endswith('.aaf'):
            output_path += '.aaf'

        with aaf2.open(output_path, 'w') as f:
            # Create master mobs for each clip
            master_mobs = {}

            for clip in self.clips:
                # Create master mob
                master = f.create.MasterMob(clip.file_name)
                f.content.mobs.append(master)
                master_mobs[clip.id] = master

                # Calculate duration in edit units
                edit_rate = aaf2.rational.AAFRational(int(self.fps * 1000), 1000)
                duration = int(clip.duration * self.fps) if clip.duration > 0 else 1

                # Add video slot
                if clip.metadata:
                    # Create source mob for the file
                    source = f.create.SourceMob()
                    f.content.mobs.append(source)

                    # Add file descriptor
                    desc = f.create.CDCIDescriptor()
                    desc['SampleRate'].value = edit_rate
                    desc['ContainerFormat'].value = f.dictionary.lookup_containerdef("AAF")
                    desc['StoredWidth'].value = clip.metadata.width or 1920
                    desc['StoredHeight'].value = clip.metadata.height or 1080
                    source.descriptor = desc

                    # Link master to source
                    master.link_external_file(source, edit_rate, duration)

            # Create composition mob (sequence)
            comp = f.create.CompositionMob()
            comp.name = f"{self.project.name} - Synced"
            f.content.mobs.append(comp)

            # Sort clips by offset
            sorted_clips = sorted(self.clips, key=lambda c: c.sync_offset_seconds)
            min_offset = min(c.sync_offset_seconds for c in sorted_clips)

            # Create timeline slot
            edit_rate = aaf2.rational.AAFRational(int(self.fps * 1000), 1000)
            timeline_slot = comp.create_timeline_slot(edit_rate)

            # Create sequence
            seq = f.create.Sequence(media_kind='Picture')
            timeline_slot.segment = seq

            # Add clips to sequence
            current_pos = 0
            for clip in sorted_clips:
                clip_offset = clip.sync_offset_seconds - min_offset
                start_frame = int(clip_offset * self.fps)
                duration = int(clip.duration * self.fps) if clip.duration > 0 else 1

                # Add filler if needed
                gap = start_frame - current_pos
                if gap > 0:
                    filler = f.create.Filler(media_kind='Picture', length=gap)
                    seq.components.append(filler)
                    current_pos = start_frame

                # Add source clip
                if clip.id in master_mobs:
                    source_ref = f.create.SourceClip(
                        mob=master_mobs[clip.id],
                        slot_id=1,
                        length=duration,
                        start_time=0
                    )
                    seq.components.append(source_ref)
                    current_pos += duration

        return output_path

    def _export_edl(self, output_path: str) -> str:
        """Export as EDL (CMX 3600 format) - fallback when AAF not available"""
        output_path = str(Path(output_path))
        if not output_path.endswith('.edl'):
            output_path += '.edl'

        lines = []

        # Header
        lines.append(f"TITLE: {self.project.name}")
        lines.append(f"FCM: {'DROP FRAME' if self.drop_frame else 'NON-DROP FRAME'}")
        lines.append("")

        # Sort clips by offset
        sorted_clips = sorted(self.clips, key=lambda c: c.sync_offset_seconds)
        min_offset = min(c.sync_offset_seconds for c in sorted_clips)

        # Track the record timeline position
        record_pos = 0.0

        for i, clip in enumerate(sorted_clips, 1):
            clip_offset = clip.sync_offset_seconds - min_offset

            # Source timecode
            src_in = "00:00:00:00"
            src_out = seconds_to_timecode(clip.duration, self.fps, self.drop_frame)

            # Record timecode
            rec_in = seconds_to_timecode(clip_offset, self.fps, self.drop_frame)
            rec_out = seconds_to_timecode(clip_offset + clip.duration, self.fps, self.drop_frame)

            # Reel name (first 8 chars of filename)
            reel = clip.file_name[:8].upper().replace(' ', '_')

            # Event line
            event_num = f"{i:03d}"
            edit_type = "V" if not clip.has_audio else "AA/V"
            lines.append(f"{event_num}  {reel:8s}  {edit_type:5s}  C        {src_in} {src_out} {rec_in} {rec_out}")

            # Source file comment
            lines.append(f"* FROM CLIP NAME: {clip.file_name}")

            # Sync confidence comment
            quality_names = {
                SyncQuality.EXCELLENT: "EXCELLENT",
                SyncQuality.GOOD: "GOOD",
                SyncQuality.FAIR: "FAIR",
                SyncQuality.POOR: "POOR",
                SyncQuality.FAILED: "FAILED",
            }
            lines.append(f"* SYNC: {quality_names.get(clip.sync_quality, 'UNKNOWN')} ({clip.sync_confidence:.1%})")
            lines.append(f"* OFFSET: {clip.sync_offset_seconds:.4f}s")
            lines.append("")

        # Write file
        with open(output_path, 'w') as f:
            f.write('\n'.join(lines))

        return output_path

    def export_avid_bin(self, output_path: str) -> str:
        """
        Export as Avid Bin (text format)

        This creates a tab-delimited file that Avid can import as a bin.
        """
        output_path = str(Path(output_path))
        if not output_path.endswith('.txt'):
            output_path += '.txt'

        lines = []

        # Header
        headers = [
            "Name", "Tracks", "Start", "End", "Duration",
            "Video", "Audio", "Camera", "Sync Confidence", "Sync Method"
        ]
        lines.append('\t'.join(headers))

        # Add clips
        for clip in self.clips:
            duration_tc = seconds_to_timecode(clip.duration, self.fps, self.drop_frame)
            offset_tc = seconds_to_timecode(clip.sync_offset_seconds, self.fps, self.drop_frame)
            end_tc = seconds_to_timecode(clip.sync_offset_seconds + clip.duration, self.fps, self.drop_frame)

            tracks = "V1A1-2" if clip.has_audio else "V1"

            row = [
                clip.file_name,
                tracks,
                offset_tc,
                end_tc,
                duration_tc,
                "Yes",
                "Yes" if clip.has_audio else "No",
                clip.camera_id or "Unknown",
                f"{clip.sync_confidence:.1%}",
                clip.sync_method.value if clip.sync_method else "N/A"
            ]
            lines.append('\t'.join(row))

        with open(output_path, 'w') as f:
            f.write('\n'.join(lines))

        return output_path
