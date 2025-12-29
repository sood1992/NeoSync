"""
Visual Analysis Engine
======================

For syncing clips without audio (DJI drones, etc.)

Methods:
- Flash/clap detection (visual spikes)
- Scene change detection
- Motion correlation
- Color histogram matching
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict, Any
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    from scipy import signal
    from scipy.ndimage import gaussian_filter1d
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


@dataclass
class VisualFingerprint:
    """Visual fingerprint for video matching"""
    file_path: str
    duration: float
    fps: float
    resolution: Tuple[int, int]

    # Time series data
    brightness_curve: np.ndarray = None  # Average brightness per frame
    motion_curve: np.ndarray = None  # Motion magnitude per frame
    scene_changes: np.ndarray = None  # Frame indices of scene changes
    flash_frames: np.ndarray = None  # Frame indices of flashes
    color_histograms: np.ndarray = None  # Color histogram per segment
    optical_flow: np.ndarray = None  # Optical flow summary


@dataclass
class VisualSyncResult:
    """Result of visual synchronization"""
    source_file: str
    target_file: str
    offset_frames: int
    offset_seconds: float
    confidence: float
    method: str
    matching_events: List[Tuple[int, int, float]] = field(default_factory=list)


class VisualAnalyzer:
    """
    Visual analyzer for syncing clips without audio
    """

    def __init__(
        self,
        target_fps: float = 30.0,
        analysis_resolution: Tuple[int, int] = (320, 180),
        use_gpu: bool = True
    ):
        self.target_fps = target_fps
        self.analysis_resolution = analysis_resolution
        self.use_gpu = use_gpu

        self._fingerprint_cache: Dict[str, VisualFingerprint] = {}
        self._cache_lock = threading.Lock()

        # GPU setup for OpenCV
        if self.use_gpu and CV2_AVAILABLE:
            self._init_gpu()
        else:
            self._gpu_enabled = False

    def _init_gpu(self):
        """Initialize GPU for OpenCV operations"""
        try:
            if cv2.cuda.getCudaEnabledDeviceCount() > 0:
                self._gpu_enabled = True
                print("✓ CUDA enabled for video processing")
            else:
                self._gpu_enabled = False
        except:
            self._gpu_enabled = False

    def analyze_video(
        self,
        file_path: str,
        max_duration: Optional[float] = None,
        progress_callback=None
    ) -> VisualFingerprint:
        """
        Analyze video for visual fingerprinting
        """
        if not CV2_AVAILABLE:
            raise ImportError("OpenCV (cv2) is required for visual analysis")

        cache_key = str(Path(file_path).resolve())

        # Check cache
        with self._cache_lock:
            if cache_key in self._fingerprint_cache:
                return self._fingerprint_cache[cache_key]

        cap = cv2.VideoCapture(file_path)

        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {file_path}")

        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = frame_count / fps if fps > 0 else 0

        if max_duration and duration > max_duration:
            frame_count = int(max_duration * fps)

        # Analysis arrays
        brightness_curve = []
        motion_curve = []
        scene_changes = []
        flash_frames = []

        prev_frame = None
        prev_gray = None
        prev_hist = None

        # Sample every N frames for efficiency
        sample_interval = max(1, int(fps / self.target_fps))

        for frame_idx in range(0, frame_count, sample_interval):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()

            if not ret:
                break

            # Resize for faster processing
            small = cv2.resize(frame, self.analysis_resolution)
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

            # Brightness
            brightness = np.mean(gray)
            brightness_curve.append(brightness)

            # Motion detection
            if prev_gray is not None:
                diff = cv2.absdiff(gray, prev_gray)
                motion = np.mean(diff)
                motion_curve.append(motion)

                # Scene change detection (histogram comparison)
                hist = cv2.calcHist([small], [0, 1, 2], None, [8, 8, 8],
                                    [0, 256, 0, 256, 0, 256])
                hist = cv2.normalize(hist, hist).flatten()

                if prev_hist is not None:
                    hist_diff = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL)
                    if hist_diff < 0.5:  # Low correlation = scene change
                        scene_changes.append(frame_idx)

                prev_hist = hist
            else:
                motion_curve.append(0)

            prev_gray = gray

            # Progress callback
            if progress_callback and frame_idx % (sample_interval * 30) == 0:
                progress_callback(frame_idx / frame_count)

        cap.release()

        # Convert to numpy arrays
        brightness_curve = np.array(brightness_curve, dtype=np.float32)
        motion_curve = np.array(motion_curve, dtype=np.float32)

        # Detect flashes (sudden brightness spikes)
        flash_frames = self._detect_flashes(brightness_curve, sample_interval)

        fingerprint = VisualFingerprint(
            file_path=file_path,
            duration=duration,
            fps=fps,
            resolution=(width, height),
            brightness_curve=brightness_curve,
            motion_curve=motion_curve,
            scene_changes=np.array(scene_changes),
            flash_frames=flash_frames
        )

        # Cache
        with self._cache_lock:
            self._fingerprint_cache[cache_key] = fingerprint

        return fingerprint

    def _detect_flashes(
        self,
        brightness: np.ndarray,
        sample_interval: int,
        threshold_std: float = 3.0
    ) -> np.ndarray:
        """
        Detect flashes (sudden brightness increases)
        """
        if len(brightness) < 10:
            return np.array([])

        # Compute derivative
        diff = np.diff(brightness)

        # Find spikes above threshold
        mean_diff = np.mean(np.abs(diff))
        std_diff = np.std(diff)
        threshold = mean_diff + threshold_std * std_diff

        flash_indices = np.where(diff > threshold)[0]

        # Convert back to original frame indices
        flash_frames = flash_indices * sample_interval

        return flash_frames

    def match_by_flash(
        self,
        fp1: VisualFingerprint,
        fp2: VisualFingerprint,
        max_offset_seconds: float = 60.0
    ) -> Optional[VisualSyncResult]:
        """
        Match videos by flash/clap detection

        Looks for simultaneous visual spikes that could indicate
        a camera flash or clapperboard.
        """
        if len(fp1.flash_frames) == 0 or len(fp2.flash_frames) == 0:
            return None

        max_offset_frames = int(max_offset_seconds * fp1.fps)
        best_offset = 0
        best_score = 0
        best_matches = []

        # Try different offsets
        for flash1 in fp1.flash_frames:
            for flash2 in fp2.flash_frames:
                offset = flash1 - flash2

                if abs(offset) > max_offset_frames:
                    continue

                # Count matching flashes at this offset
                matches = []
                for f1 in fp1.flash_frames:
                    expected_f2 = f1 - offset
                    # Find closest flash in fp2
                    if len(fp2.flash_frames) > 0:
                        closest_idx = np.argmin(np.abs(fp2.flash_frames - expected_f2))
                        closest_f2 = fp2.flash_frames[closest_idx]
                        error = abs(closest_f2 - expected_f2)
                        if error < fp1.fps * 0.5:  # Within 0.5 seconds
                            matches.append((f1, closest_f2, error))

                if len(matches) > best_score:
                    best_score = len(matches)
                    best_offset = offset
                    best_matches = matches

        if best_score == 0:
            return None

        confidence = min(1.0, best_score / max(len(fp1.flash_frames), 1))

        return VisualSyncResult(
            source_file=fp1.file_path,
            target_file=fp2.file_path,
            offset_frames=best_offset,
            offset_seconds=best_offset / fp1.fps,
            confidence=confidence,
            method="flash_detection",
            matching_events=best_matches
        )

    def match_by_motion(
        self,
        fp1: VisualFingerprint,
        fp2: VisualFingerprint,
        max_offset_seconds: float = 60.0
    ) -> Optional[VisualSyncResult]:
        """
        Match videos by motion correlation

        Useful for multi-camera shoots where cameras move together
        (e.g., on a vehicle, or shooting the same action).
        """
        if fp1.motion_curve is None or fp2.motion_curve is None:
            return None

        if len(fp1.motion_curve) < 100 or len(fp2.motion_curve) < 100:
            return None

        motion1 = fp1.motion_curve
        motion2 = fp2.motion_curve

        # Normalize
        motion1 = (motion1 - np.mean(motion1)) / (np.std(motion1) + 1e-10)
        motion2 = (motion2 - np.mean(motion2)) / (np.std(motion2) + 1e-10)

        # Cross-correlation
        correlation = signal.correlate(motion1, motion2, mode='full')
        lags = signal.correlation_lags(len(motion1), len(motion2), mode='full')

        # Find peak
        max_lag_samples = int(max_offset_seconds * self.target_fps)
        valid_range = np.abs(lags) <= max_lag_samples
        valid_corr = correlation.copy()
        valid_corr[~valid_range] = -np.inf

        peak_idx = np.argmax(valid_corr)
        peak_lag = lags[peak_idx]
        peak_value = correlation[peak_idx]

        # Normalize confidence
        confidence = peak_value / (len(motion1) + len(motion2))
        confidence = min(1.0, max(0.0, confidence))

        # Convert lag to frame offset (accounting for sample interval)
        sample_interval = max(1, int(fp1.fps / self.target_fps))
        offset_frames = peak_lag * sample_interval

        return VisualSyncResult(
            source_file=fp1.file_path,
            target_file=fp2.file_path,
            offset_frames=offset_frames,
            offset_seconds=offset_frames / fp1.fps,
            confidence=confidence,
            method="motion_correlation"
        )

    def match_by_scene_changes(
        self,
        fp1: VisualFingerprint,
        fp2: VisualFingerprint,
        max_offset_seconds: float = 60.0
    ) -> Optional[VisualSyncResult]:
        """
        Match videos by scene change timing

        Scene changes (cuts, flashes, etc.) should happen at the
        same time in synchronized clips.
        """
        if len(fp1.scene_changes) < 3 or len(fp2.scene_changes) < 3:
            return None

        max_offset_frames = int(max_offset_seconds * fp1.fps)

        # Similar to flash matching
        best_offset = 0
        best_score = 0

        for sc1 in fp1.scene_changes[:20]:  # Limit search
            for sc2 in fp2.scene_changes[:20]:
                offset = sc1 - sc2

                if abs(offset) > max_offset_frames:
                    continue

                # Count matching scene changes
                score = 0
                for s1 in fp1.scene_changes:
                    expected_s2 = s1 - offset
                    if len(fp2.scene_changes) > 0:
                        errors = np.abs(fp2.scene_changes - expected_s2)
                        if np.min(errors) < fp1.fps * 1.0:  # Within 1 second
                            score += 1

                if score > best_score:
                    best_score = score
                    best_offset = offset

        if best_score < 3:
            return None

        confidence = min(1.0, best_score / max(len(fp1.scene_changes), 10))

        return VisualSyncResult(
            source_file=fp1.file_path,
            target_file=fp2.file_path,
            offset_frames=best_offset,
            offset_seconds=best_offset / fp1.fps,
            confidence=confidence,
            method="scene_change_matching"
        )

    def match_by_brightness(
        self,
        fp1: VisualFingerprint,
        fp2: VisualFingerprint,
        max_offset_seconds: float = 60.0
    ) -> Optional[VisualSyncResult]:
        """
        Match videos by overall brightness correlation

        Works when clips are shot in the same lighting conditions
        with natural brightness variations.
        """
        if fp1.brightness_curve is None or fp2.brightness_curve is None:
            return None

        if len(fp1.brightness_curve) < 100 or len(fp2.brightness_curve) < 100:
            return None

        bright1 = fp1.brightness_curve
        bright2 = fp2.brightness_curve

        # High-pass filter to remove DC offset
        if SCIPY_AVAILABLE:
            bright1 = bright1 - gaussian_filter1d(bright1, sigma=30)
            bright2 = bright2 - gaussian_filter1d(bright2, sigma=30)

        # Normalize
        bright1 = (bright1 - np.mean(bright1)) / (np.std(bright1) + 1e-10)
        bright2 = (bright2 - np.mean(bright2)) / (np.std(bright2) + 1e-10)

        # Cross-correlation
        correlation = signal.correlate(bright1, bright2, mode='full')
        lags = signal.correlation_lags(len(bright1), len(bright2), mode='full')

        max_lag_samples = int(max_offset_seconds * self.target_fps)
        valid_range = np.abs(lags) <= max_lag_samples
        valid_corr = correlation.copy()
        valid_corr[~valid_range] = -np.inf

        peak_idx = np.argmax(valid_corr)
        peak_lag = lags[peak_idx]
        peak_value = correlation[peak_idx]

        confidence = peak_value / len(bright1)
        confidence = min(1.0, max(0.0, confidence))

        sample_interval = max(1, int(fp1.fps / self.target_fps))
        offset_frames = peak_lag * sample_interval

        return VisualSyncResult(
            source_file=fp1.file_path,
            target_file=fp2.file_path,
            offset_frames=offset_frames,
            offset_seconds=offset_frames / fp1.fps,
            confidence=confidence,
            method="brightness_correlation"
        )

    def find_best_visual_sync(
        self,
        fp1: VisualFingerprint,
        fp2: VisualFingerprint,
        max_offset_seconds: float = 60.0
    ) -> Optional[VisualSyncResult]:
        """
        Try all visual sync methods and return best result
        """
        results = []

        # Try flash matching first (most reliable)
        flash_result = self.match_by_flash(fp1, fp2, max_offset_seconds)
        if flash_result and flash_result.confidence > 0.3:
            results.append(flash_result)

        # Try scene change matching
        scene_result = self.match_by_scene_changes(fp1, fp2, max_offset_seconds)
        if scene_result and scene_result.confidence > 0.3:
            results.append(scene_result)

        # Try motion correlation
        motion_result = self.match_by_motion(fp1, fp2, max_offset_seconds)
        if motion_result and motion_result.confidence > 0.3:
            results.append(motion_result)

        # Try brightness correlation
        bright_result = self.match_by_brightness(fp1, fp2, max_offset_seconds)
        if bright_result and bright_result.confidence > 0.2:
            results.append(bright_result)

        if not results:
            return None

        # Return highest confidence result
        return max(results, key=lambda r: r.confidence)

    def batch_analyze(
        self,
        file_paths: List[str],
        progress_callback=None,
        max_workers: int = 2
    ) -> List[VisualFingerprint]:
        """
        Analyze multiple videos in parallel

        Note: Video analysis is I/O and CPU intensive,
        so fewer workers is often better.
        """
        fingerprints = []
        total = len(file_paths)

        def process_file(idx_path):
            idx, path = idx_path
            try:
                def local_progress(p):
                    if progress_callback:
                        overall = (idx + p) / total
                        progress_callback(overall, path)

                fp = self.analyze_video(path, progress_callback=local_progress)
                return fp
            except Exception as e:
                print(f"Error analyzing {path}: {e}")
                return None

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(process_file, enumerate(file_paths)))

        return [r for r in results if r is not None]

    def clear_cache(self):
        """Clear the fingerprint cache"""
        with self._cache_lock:
            self._fingerprint_cache.clear()
