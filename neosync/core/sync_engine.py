"""
NeoSync Core Sync Engine
========================

The heart of NeoSync - orchestrates all sync methods:
1. Audio waveform matching (GCC-PHAT)
2. Audio fingerprint matching
3. Visual sync (flash, motion, scene)
4. Timecode matching
5. Metadata correlation
6. Confidence fusion

Handles 5-500+ clips with parallel processing.
"""

import os
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Callable, Any
from enum import Enum, auto
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
import hashlib

from .audio_analyzer import AudioAnalyzer, AudioFingerprint, SyncResult, SyncMethod
from .visual_analyzer import VisualAnalyzer, VisualFingerprint, VisualSyncResult
from .metadata_extractor import MetadataExtractor, MediaMetadata, Timecode


class SyncStatus(Enum):
    """Status of sync for each clip"""
    PENDING = auto()
    ANALYZING = auto()
    SYNCED = auto()
    SYNCED_LOW_CONFIDENCE = auto()
    FAILED = auto()
    REFERENCE = auto()
    MANUAL = auto()


class SyncQuality(Enum):
    """Quality level of sync"""
    EXCELLENT = auto()  # >95% confidence
    GOOD = auto()       # 80-95% confidence
    FAIR = auto()       # 60-80% confidence
    POOR = auto()       # 40-60% confidence
    FAILED = auto()     # <40% confidence


@dataclass
class ClipInfo:
    """Complete information about a clip"""
    id: str
    file_path: str
    file_name: str

    # Metadata
    metadata: Optional[MediaMetadata] = None

    # Fingerprints
    audio_fingerprint: Optional[AudioFingerprint] = None
    visual_fingerprint: Optional[VisualFingerprint] = None

    # Sync results
    sync_status: SyncStatus = SyncStatus.PENDING
    sync_offset_seconds: float = 0.0
    sync_offset_frames: int = 0
    sync_confidence: float = 0.0
    sync_method: Optional[SyncMethod] = None
    sync_quality: SyncQuality = SyncQuality.FAILED
    drift_rate: float = 0.0

    # For multicam grouping
    camera_id: Optional[str] = None
    group_id: Optional[str] = None

    # UI state
    color_code: str = "#808080"  # Gray = pending
    is_reference: bool = False
    is_selected: bool = False

    # Error info
    error_message: Optional[str] = None

    def __post_init__(self):
        if self.id is None:
            self.id = hashlib.md5(self.file_path.encode()).hexdigest()[:12]

    @property
    def has_audio(self) -> bool:
        return self.metadata.has_audio if self.metadata else False

    @property
    def duration(self) -> float:
        return self.metadata.duration_seconds if self.metadata else 0.0

    @property
    def fps(self) -> float:
        return self.metadata.fps if self.metadata else 24.0


@dataclass
class SyncGroup:
    """A group of synchronized clips"""
    id: str
    name: str
    clips: List[ClipInfo] = field(default_factory=list)
    reference_clip: Optional[ClipInfo] = None
    timeline_start: float = 0.0  # Start time on unified timeline
    timeline_duration: float = 0.0
    color: str = "#4A90D9"

    @property
    def clip_count(self) -> int:
        return len(self.clips)


@dataclass
class SyncProject:
    """Complete sync project state"""
    name: str = "Untitled Project"
    clips: List[ClipInfo] = field(default_factory=list)
    groups: List[SyncGroup] = field(default_factory=list)
    reference_clip: Optional[ClipInfo] = None

    # Settings
    sample_rate: int = 48000
    max_offset_seconds: float = 3600.0  # 1 hour max offset
    drift_correction: bool = True
    noise_reduction: bool = True
    use_gpu: bool = True

    # Stats
    total_synced: int = 0
    total_failed: int = 0
    average_confidence: float = 0.0

    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)


class SyncEngine:
    """
    Main synchronization engine

    Workflow:
    1. Add clips to project
    2. Analyze all clips (parallel)
    3. Find reference clip (or let user choose)
    4. Sync all clips to reference
    5. Refine with multi-point drift correction
    6. Export results
    """

    # Color codes for sync quality
    COLORS = {
        SyncQuality.EXCELLENT: "#22C55E",  # Green
        SyncQuality.GOOD: "#84CC16",       # Lime
        SyncQuality.FAIR: "#EAB308",       # Yellow
        SyncQuality.POOR: "#F97316",       # Orange
        SyncQuality.FAILED: "#EF4444",     # Red
    }

    def __init__(
        self,
        sample_rate: int = 48000,
        use_gpu: bool = True,
        noise_reduction: bool = True,
        max_workers: int = None
    ):
        self.sample_rate = sample_rate
        self.use_gpu = use_gpu
        self.noise_reduction = noise_reduction
        self.max_workers = max_workers or min(8, (os.cpu_count() or 4))

        # Initialize analyzers
        self.audio_analyzer = AudioAnalyzer(
            sample_rate=sample_rate,
            use_gpu=use_gpu,
            noise_reduction=noise_reduction
        )
        self.visual_analyzer = VisualAnalyzer(use_gpu=use_gpu)
        self.metadata_extractor = MetadataExtractor()

        # Current project
        self.project = SyncProject()

        # Callbacks
        self._progress_callback: Optional[Callable] = None
        self._status_callback: Optional[Callable] = None

        # Threading
        self._lock = threading.Lock()
        self._cancel_flag = False

    def set_progress_callback(self, callback: Callable[[float, str], None]):
        """Set callback for progress updates: callback(progress: 0-1, message: str)"""
        self._progress_callback = callback

    def set_status_callback(self, callback: Callable[[ClipInfo], None]):
        """Set callback for clip status updates"""
        self._status_callback = callback

    def _report_progress(self, progress: float, message: str):
        """Report progress to callback"""
        if self._progress_callback:
            self._progress_callback(progress, message)

    def _report_status(self, clip: ClipInfo):
        """Report clip status change"""
        if self._status_callback:
            self._status_callback(clip)

    def add_clips(self, file_paths: List[str]) -> List[ClipInfo]:
        """Add clips to the project"""
        added = []
        for path in file_paths:
            path = str(Path(path).resolve())

            # Check if already added
            existing = [c for c in self.project.clips if c.file_path == path]
            if existing:
                continue

            clip = ClipInfo(
                id=None,
                file_path=path,
                file_name=Path(path).name
            )
            self.project.clips.append(clip)
            added.append(clip)

        self.project.modified_at = time.time()
        return added

    def remove_clips(self, clip_ids: List[str]):
        """Remove clips from the project"""
        self.project.clips = [c for c in self.project.clips if c.id not in clip_ids]
        self.project.modified_at = time.time()

    def clear_project(self):
        """Clear all clips from project"""
        self.project = SyncProject()
        self.audio_analyzer.clear_cache()
        self.visual_analyzer.clear_cache()
        self.metadata_extractor.clear_cache()

    def analyze_clips(
        self,
        clips: Optional[List[ClipInfo]] = None,
        analyze_audio: bool = True,
        analyze_visual: bool = True,
        analyze_metadata: bool = True
    ) -> bool:
        """
        Analyze all clips in parallel

        Returns True if successful, False if cancelled
        """
        if clips is None:
            clips = self.project.clips

        if not clips:
            return True

        self._cancel_flag = False
        total = len(clips)
        completed = 0

        def analyze_single(clip: ClipInfo):
            nonlocal completed

            if self._cancel_flag:
                return

            clip.sync_status = SyncStatus.ANALYZING
            self._report_status(clip)

            try:
                # Extract metadata
                if analyze_metadata:
                    clip.metadata = self.metadata_extractor.extract(clip.file_path)
                    clip.camera_id = clip.metadata.camera_id

                # Audio fingerprint
                if analyze_audio and clip.has_audio:
                    clip.audio_fingerprint = self.audio_analyzer.compute_fingerprint(
                        clip.file_path
                    )

                # Visual fingerprint (for all clips, essential for audio-less)
                if analyze_visual:
                    clip.visual_fingerprint = self.visual_analyzer.analyze_video(
                        clip.file_path
                    )

                clip.sync_status = SyncStatus.PENDING  # Ready for sync

            except Exception as e:
                clip.sync_status = SyncStatus.FAILED
                clip.error_message = str(e)
                clip.color_code = self.COLORS[SyncQuality.FAILED]

            self._report_status(clip)

            with self._lock:
                completed += 1
                progress = completed / total
                self._report_progress(progress, f"Analyzed {completed}/{total}: {clip.file_name}")

        # Process in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(analyze_single, clip) for clip in clips]
            for future in as_completed(futures):
                if self._cancel_flag:
                    return False
                try:
                    future.result()
                except Exception as e:
                    print(f"Analysis error: {e}")

        return not self._cancel_flag

    def find_best_reference(self) -> Optional[ClipInfo]:
        """
        Automatically find the best reference clip

        Criteria:
        - Longest duration
        - Has audio
        - Good audio quality (high energy variance)
        """
        candidates = [c for c in self.project.clips
                      if c.has_audio and c.audio_fingerprint is not None]

        if not candidates:
            # Fall back to any clip with visual fingerprint
            candidates = [c for c in self.project.clips
                          if c.visual_fingerprint is not None]

        if not candidates:
            return None

        def score_clip(clip: ClipInfo) -> float:
            score = 0.0

            # Duration score (longer is better, up to 10 minutes)
            score += min(clip.duration / 600, 1.0) * 30

            # Audio quality score
            if clip.audio_fingerprint:
                energy = clip.audio_fingerprint.energy_envelope
                if energy is not None and len(energy) > 0:
                    # High variance means more dynamic audio (better for matching)
                    variance = np.var(energy)
                    score += min(variance * 100, 30)

                    # Many onsets means more transients (better for matching)
                    if clip.audio_fingerprint.onset_frames is not None:
                        onset_density = len(clip.audio_fingerprint.onset_frames) / clip.duration
                        score += min(onset_density * 5, 20)

            # Has timecode (useful for verification)
            if clip.metadata and clip.metadata.start_timecode:
                score += 10

            return score

        best = max(candidates, key=score_clip)
        return best

    def set_reference(self, clip: ClipInfo):
        """Set a clip as the sync reference"""
        # Clear previous reference
        if self.project.reference_clip:
            self.project.reference_clip.is_reference = False
            self.project.reference_clip.sync_status = SyncStatus.PENDING

        clip.is_reference = True
        clip.sync_status = SyncStatus.REFERENCE
        clip.sync_offset_seconds = 0.0
        clip.sync_confidence = 1.0
        clip.sync_quality = SyncQuality.EXCELLENT
        clip.color_code = "#3B82F6"  # Blue for reference

        self.project.reference_clip = clip
        self._report_status(clip)

    def sync_all(
        self,
        reference: Optional[ClipInfo] = None,
        max_offset_seconds: float = 3600.0,
        use_drift_correction: bool = True
    ) -> bool:
        """
        Sync all clips to the reference

        Returns True if successful
        """
        if reference is None:
            reference = self.project.reference_clip or self.find_best_reference()

        if reference is None:
            return False

        self.set_reference(reference)
        self._cancel_flag = False

        clips_to_sync = [c for c in self.project.clips
                         if c.id != reference.id and c.sync_status != SyncStatus.SYNCED]

        total = len(clips_to_sync)
        if total == 0:
            return True

        completed = 0

        for clip in clips_to_sync:
            if self._cancel_flag:
                return False

            self._report_progress(completed / total, f"Syncing: {clip.file_name}")

            result = self._sync_clip_to_reference(
                clip, reference, max_offset_seconds, use_drift_correction
            )

            if result:
                self._apply_sync_result(clip, result)
            else:
                # Try visual sync if audio failed
                visual_result = self._visual_sync_clip(clip, reference, max_offset_seconds)
                if visual_result:
                    self._apply_visual_sync_result(clip, visual_result)
                else:
                    # Try metadata/timecode sync as last resort
                    tc_result = self._timecode_sync_clip(clip, reference)
                    if tc_result:
                        clip.sync_offset_seconds = tc_result
                        clip.sync_confidence = 0.5
                        clip.sync_method = SyncMethod.TIMECODE
                        clip.sync_quality = SyncQuality.FAIR
                        clip.sync_status = SyncStatus.SYNCED_LOW_CONFIDENCE
                        clip.color_code = self.COLORS[SyncQuality.FAIR]
                    else:
                        clip.sync_status = SyncStatus.FAILED
                        clip.sync_quality = SyncQuality.FAILED
                        clip.color_code = self.COLORS[SyncQuality.FAILED]

            self._report_status(clip)
            completed += 1

        self._update_project_stats()
        self._report_progress(1.0, f"Sync complete: {self.project.total_synced}/{total} synced")

        return True

    def _sync_clip_to_reference(
        self,
        clip: ClipInfo,
        reference: ClipInfo,
        max_offset_seconds: float,
        use_drift_correction: bool
    ) -> Optional[SyncResult]:
        """
        Sync a single clip to reference using tiered audio approach

        Priority order (fast → accurate):
        1. Multi-scale sync (fastest, good for most cases)
        2. Standard GCC-PHAT (if multi-scale confidence is low)
        3. Ensemble sync (slowest, but most accurate for difficult cases)
        """
        if not clip.has_audio or not reference.has_audio:
            return None

        if clip.audio_fingerprint is None or reference.audio_fingerprint is None:
            return None

        try:
            # Load audio samples
            clip_audio, _ = self.audio_analyzer.load_audio(clip.file_path)
            ref_audio, _ = self.audio_analyzer.load_audio(reference.file_path)

            # Quick fingerprint check first (instant)
            fp1 = clip.audio_fingerprint.fingerprint
            fp2 = reference.audio_fingerprint.fingerprint
            fp_similarity = np.dot(fp1, fp2) / (np.linalg.norm(fp1) * np.linalg.norm(fp2) + 1e-10)

            if fp_similarity < 0.3:
                # Fingerprints too different, likely different audio
                return None

            max_delay_samples = int(max_offset_seconds * self.sample_rate)

            # ===== TIER 1: Multi-scale sync (fastest) =====
            # Only use for longer clips where multi-scale helps
            delay = None
            confidence = 0.0
            correlation = None

            if len(clip_audio) > self.sample_rate * 30:  # >30 seconds
                try:
                    delay, confidence = self.audio_analyzer.multi_scale_sync(
                        clip_audio, ref_audio, self.sample_rate
                    )
                    # Multi-scale doesn't return correlation, get it for sub-sample
                    if confidence > 0.6:  # Good enough, use this result
                        _, _, correlation = self.audio_analyzer.gcc_phat(
                            clip_audio, ref_audio, max_delay=max_delay_samples
                        )
                except:
                    pass

            # ===== TIER 2: Standard GCC-PHAT (fast, reliable) =====
            if confidence < 0.6:
                delay, confidence, correlation = self.audio_analyzer.gcc_phat(
                    clip_audio, ref_audio, max_delay=max_delay_samples
                )

            # ===== TIER 3: Ensemble sync (slow, for difficult cases) =====
            if confidence < 0.4 and len(clip_audio) < self.sample_rate * 300:  # <5 min
                try:
                    delay, confidence, metrics = self.audio_analyzer.ensemble_sync(
                        clip_audio, ref_audio, self.sample_rate,
                        max_offset_seconds=min(max_offset_seconds, 120)
                    )
                    # Get correlation for sub-sample refinement
                    _, _, correlation = self.audio_analyzer.gcc_phat(
                        clip_audio, ref_audio, max_delay=max_delay_samples
                    )
                except:
                    pass

            if confidence < 0.1 or delay is None:
                return None

            # Sub-sample refinement
            sub_sample = 0.0
            if correlation is not None:
                center = len(correlation) // 2
                peak_idx = center + delay
                if 0 <= peak_idx < len(correlation):
                    sub_sample = self.audio_analyzer.subsample_refinement(correlation, peak_idx)

            # Drift detection (only for longer clips)
            drift_rate = 0.0
            if use_drift_correction and len(clip_audio) > self.sample_rate * 30:
                try:
                    drift_rate, _ = self.audio_analyzer.detect_drift(
                        clip_audio, ref_audio, self.sample_rate
                    )
                except:
                    pass

            return SyncResult(
                source_file=clip.file_path,
                target_file=reference.file_path,
                offset_samples=delay,
                offset_seconds=delay / self.sample_rate,
                confidence=confidence,
                method_used=SyncMethod.AUDIO_WAVEFORM,
                drift_rate=drift_rate,
                sub_sample_offset=sub_sample,
                quality_metrics={
                    'fingerprint_similarity': float(fp_similarity),
                    'gcc_phat_peak': float(confidence)
                }
            )

        except Exception as e:
            print(f"Audio sync error for {clip.file_name}: {e}")
            return None

    def _visual_sync_clip(
        self,
        clip: ClipInfo,
        reference: ClipInfo,
        max_offset_seconds: float
    ) -> Optional[VisualSyncResult]:
        """Sync clip using visual methods (for audio-less clips)"""
        if clip.visual_fingerprint is None or reference.visual_fingerprint is None:
            return None

        try:
            result = self.visual_analyzer.find_best_visual_sync(
                clip.visual_fingerprint,
                reference.visual_fingerprint,
                max_offset_seconds
            )
            return result

        except Exception as e:
            print(f"Visual sync error for {clip.file_name}: {e}")
            return None

    def _timecode_sync_clip(
        self,
        clip: ClipInfo,
        reference: ClipInfo
    ) -> Optional[float]:
        """Sync clip using timecode"""
        if clip.metadata is None or reference.metadata is None:
            return None

        clip_tc = clip.metadata.start_timecode
        ref_tc = reference.metadata.start_timecode

        if clip_tc and ref_tc:
            offset = clip_tc.to_seconds() - ref_tc.to_seconds()
            return offset

        # Try creation time
        clip_time = clip.metadata.recording_time or clip.metadata.creation_time
        ref_time = reference.metadata.recording_time or reference.metadata.creation_time

        if clip_time and ref_time:
            offset = (clip_time - ref_time).total_seconds()
            return offset

        return None

    def _apply_sync_result(self, clip: ClipInfo, result: SyncResult):
        """Apply audio sync result to clip"""
        clip.sync_offset_seconds = result.total_offset_seconds
        clip.sync_offset_frames = int(result.offset_seconds * clip.fps)
        clip.sync_confidence = result.confidence
        clip.sync_method = result.method_used
        clip.drift_rate = result.drift_rate

        # Determine quality
        if result.confidence >= 0.95:
            clip.sync_quality = SyncQuality.EXCELLENT
            clip.sync_status = SyncStatus.SYNCED
        elif result.confidence >= 0.80:
            clip.sync_quality = SyncQuality.GOOD
            clip.sync_status = SyncStatus.SYNCED
        elif result.confidence >= 0.60:
            clip.sync_quality = SyncQuality.FAIR
            clip.sync_status = SyncStatus.SYNCED
        elif result.confidence >= 0.40:
            clip.sync_quality = SyncQuality.POOR
            clip.sync_status = SyncStatus.SYNCED_LOW_CONFIDENCE
        else:
            clip.sync_quality = SyncQuality.FAILED
            clip.sync_status = SyncStatus.FAILED

        clip.color_code = self.COLORS[clip.sync_quality]

    def _apply_visual_sync_result(self, clip: ClipInfo, result: VisualSyncResult):
        """Apply visual sync result to clip"""
        clip.sync_offset_seconds = result.offset_seconds
        clip.sync_offset_frames = result.offset_frames
        clip.sync_confidence = result.confidence
        clip.sync_method = SyncMethod.VISUAL_FLASH  # Simplified

        # Visual sync is less reliable, adjust quality thresholds
        if result.confidence >= 0.85:
            clip.sync_quality = SyncQuality.GOOD
            clip.sync_status = SyncStatus.SYNCED
        elif result.confidence >= 0.60:
            clip.sync_quality = SyncQuality.FAIR
            clip.sync_status = SyncStatus.SYNCED
        elif result.confidence >= 0.40:
            clip.sync_quality = SyncQuality.POOR
            clip.sync_status = SyncStatus.SYNCED_LOW_CONFIDENCE
        else:
            clip.sync_quality = SyncQuality.FAILED
            clip.sync_status = SyncStatus.FAILED

        clip.color_code = self.COLORS[clip.sync_quality]

    def _update_project_stats(self):
        """Update project statistics"""
        synced = [c for c in self.project.clips
                  if c.sync_status in (SyncStatus.SYNCED, SyncStatus.SYNCED_LOW_CONFIDENCE, SyncStatus.REFERENCE)]
        failed = [c for c in self.project.clips if c.sync_status == SyncStatus.FAILED]

        self.project.total_synced = len(synced)
        self.project.total_failed = len(failed)

        if synced:
            self.project.average_confidence = np.mean([c.sync_confidence for c in synced])

    def auto_group_by_camera(self):
        """Automatically group clips by camera"""
        groups: Dict[str, List[ClipInfo]] = {}

        for clip in self.project.clips:
            camera_id = clip.camera_id or "Unknown"
            if camera_id not in groups:
                groups[camera_id] = []
            groups[camera_id].append(clip)

        self.project.groups = []
        colors = ["#4A90D9", "#D94A4A", "#4AD94A", "#D9D94A", "#D94AD9", "#4AD9D9"]

        for i, (camera_id, clips) in enumerate(groups.items()):
            group = SyncGroup(
                id=f"group_{i}",
                name=camera_id,
                clips=clips,
                color=colors[i % len(colors)]
            )

            # Set reference as the longest clip with audio
            audio_clips = [c for c in clips if c.has_audio]
            if audio_clips:
                group.reference_clip = max(audio_clips, key=lambda c: c.duration)

            self.project.groups.append(group)

    def manual_adjust_offset(self, clip: ClipInfo, offset_delta_seconds: float):
        """Manually adjust a clip's sync offset"""
        clip.sync_offset_seconds += offset_delta_seconds
        clip.sync_offset_frames = int(clip.sync_offset_seconds * clip.fps)
        clip.sync_status = SyncStatus.MANUAL
        clip.color_code = "#9333EA"  # Purple for manual
        self._report_status(clip)

    def cancel(self):
        """Cancel ongoing operation"""
        self._cancel_flag = True

    def get_timeline_data(self) -> Dict[str, Any]:
        """Get data for timeline visualization"""
        if not self.project.clips:
            return {'clips': [], 'duration': 0}

        # Find timeline bounds
        min_offset = min(c.sync_offset_seconds for c in self.project.clips)
        max_end = max(c.sync_offset_seconds + c.duration for c in self.project.clips)

        timeline_clips = []
        for clip in self.project.clips:
            timeline_clips.append({
                'id': clip.id,
                'name': clip.file_name,
                'start': clip.sync_offset_seconds - min_offset,
                'duration': clip.duration,
                'color': clip.color_code,
                'status': clip.sync_status.name,
                'confidence': clip.sync_confidence,
                'camera': clip.camera_id,
                'has_audio': clip.has_audio
            })

        return {
            'clips': timeline_clips,
            'duration': max_end - min_offset,
            'offset': min_offset
        }
