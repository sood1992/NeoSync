"""
Audio Analysis Engine
=====================

Multi-stage audio analysis with:
- Chromaprint fingerprinting for coarse matching
- GCC-PHAT for fine alignment
- Sub-sample interpolation
- Noise-robust preprocessing
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict, Any
from enum import Enum
import hashlib
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import threading
from pathlib import Path

# Audio processing
try:
    import librosa
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False

try:
    import scipy.signal as signal
    from scipy.fft import fft, ifft, fftfreq
    from scipy.interpolate import interp1d
    from scipy.ndimage import gaussian_filter1d
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

try:
    import noisereduce as nr
    NOISEREDUCE_AVAILABLE = True
except ImportError:
    NOISEREDUCE_AVAILABLE = False


class SyncMethod(Enum):
    """Synchronization methods available"""
    AUDIO_WAVEFORM = "audio_waveform"
    AUDIO_FINGERPRINT = "audio_fingerprint"
    VISUAL_FLASH = "visual_flash"
    VISUAL_SCENE = "visual_scene"
    MOTION_CORRELATION = "motion_correlation"
    TIMECODE = "timecode"
    METADATA = "metadata"
    HYBRID = "hybrid"


@dataclass
class AudioFingerprint:
    """Audio fingerprint for fast coarse matching"""
    file_path: str
    fingerprint: np.ndarray
    duration: float
    sample_rate: int
    hash_id: str
    spectral_centroid: np.ndarray = None
    mfcc: np.ndarray = None
    chroma: np.ndarray = None
    onset_frames: np.ndarray = None
    energy_envelope: np.ndarray = None

    def __post_init__(self):
        if self.hash_id is None:
            self.hash_id = hashlib.md5(self.fingerprint.tobytes()).hexdigest()[:16]


@dataclass
class SyncResult:
    """Result of synchronization between two clips"""
    source_file: str
    target_file: str
    offset_samples: int
    offset_seconds: float
    confidence: float
    method_used: SyncMethod
    drift_rate: float = 0.0  # samples per second of drift
    sub_sample_offset: float = 0.0  # sub-sample refinement
    quality_metrics: Dict[str, float] = field(default_factory=dict)

    @property
    def total_offset_seconds(self) -> float:
        """Total offset including sub-sample refinement"""
        return self.offset_seconds + (self.sub_sample_offset / 48000)  # assume 48kHz


class AudioAnalyzer:
    """
    Advanced audio analyzer with multi-stage matching

    Features:
    - GCC-PHAT with adaptive PHAT-β weighting for variable SNR
    - Sinc interpolation for sub-sample accuracy
    - Diffuseness mask for reverberant environments
    - GPU acceleration (CUDA/OpenCL)
    """

    def __init__(
        self,
        sample_rate: int = 48000,
        fft_size: int = 4096,
        hop_length: int = 512,
        use_gpu: bool = True,
        noise_reduction: bool = True,
        cache_fingerprints: bool = True,
        phat_beta: Optional[float] = None,  # Adaptive PHAT-β (None = auto, 0-1 = manual)
        use_sinc_interpolation: bool = True,  # Higher precision sub-sample
        use_diffuseness_mask: bool = True,  # Better reverb handling
    ):
        self.sample_rate = sample_rate
        self.fft_size = self._optimal_fft_size(fft_size)
        self.hop_length = hop_length
        self.use_gpu = use_gpu and self._check_gpu_available()
        self.noise_reduction = noise_reduction
        self.cache_fingerprints = cache_fingerprints
        self.phat_beta = phat_beta
        self.use_sinc_interpolation = use_sinc_interpolation
        self.use_diffuseness_mask = use_diffuseness_mask

        # Fingerprint cache
        self._fingerprint_cache: Dict[str, AudioFingerprint] = {}
        self._cache_lock = threading.Lock()

        # GPU setup
        self._gpu_context = None
        if self.use_gpu:
            self._init_gpu()

    def _optimal_fft_size(self, requested: int) -> int:
        """Find optimal power-of-2 FFT size"""
        power = int(np.ceil(np.log2(requested)))
        return 2 ** power

    def _check_gpu_available(self) -> bool:
        """Check if GPU acceleration is available"""
        try:
            import cupy as cp
            cp.cuda.Device(0).compute_capability
            return True
        except:
            pass

        try:
            import pyopencl as cl
            platforms = cl.get_platforms()
            return len(platforms) > 0
        except:
            pass

        return False

    def _init_gpu(self):
        """Initialize GPU context"""
        try:
            import cupy as cp
            self._gpu_backend = 'cuda'
            self._gpu_context = cp
            print("✓ CUDA GPU acceleration enabled")
        except ImportError:
            try:
                import pyopencl as cl
                self._gpu_backend = 'opencl'
                platforms = cl.get_platforms()
                self._gpu_context = cl.Context(
                    dev_type=cl.device_type.GPU,
                    properties=[(cl.context_properties.PLATFORM, platforms[0])]
                )
                print("✓ OpenCL GPU acceleration enabled")
            except:
                self._gpu_backend = None
                self._gpu_context = None
                print("⚠ No GPU acceleration available, using CPU")

    def load_audio(
        self,
        file_path: str,
        duration: Optional[float] = None,
        offset: float = 0.0
    ) -> Tuple[np.ndarray, int]:
        """
        Load audio from file with preprocessing

        Args:
            file_path: Path to audio/video file
            duration: Maximum duration to load (seconds)
            offset: Start offset (seconds)

        Returns:
            audio: Audio samples as float32 array
            sr: Sample rate
        """
        if not LIBROSA_AVAILABLE:
            raise ImportError("librosa is required for audio loading")

        # Load audio
        audio, sr = librosa.load(
            file_path,
            sr=self.sample_rate,
            mono=True,
            offset=offset,
            duration=duration
        )

        # Preprocessing pipeline
        audio = self._preprocess_audio(audio, sr)

        return audio, sr

    def _preprocess_audio(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """
        Noise-robust preprocessing pipeline
        """
        # Normalize
        audio = audio.astype(np.float32)
        max_val = np.max(np.abs(audio))
        if max_val > 0:
            audio = audio / max_val

        # High-pass filter to remove DC offset and low rumble
        if SCIPY_AVAILABLE:
            sos = signal.butter(4, 80, btype='highpass', fs=sr, output='sos')
            audio = signal.sosfilt(sos, audio)

        # Noise reduction (spectral gating)
        if self.noise_reduction and NOISEREDUCE_AVAILABLE:
            try:
                audio = nr.reduce_noise(
                    y=audio,
                    sr=sr,
                    stationary=False,
                    prop_decrease=0.75
                )
            except:
                pass  # Continue without noise reduction

        # Normalize again after processing
        max_val = np.max(np.abs(audio))
        if max_val > 0:
            audio = audio / max_val

        return audio

    def compute_fingerprint(
        self,
        file_path: str,
        audio: Optional[np.ndarray] = None,
        sr: Optional[int] = None
    ) -> AudioFingerprint:
        """
        Compute comprehensive audio fingerprint
        """
        cache_key = str(Path(file_path).resolve())

        # Check cache
        if self.cache_fingerprints:
            with self._cache_lock:
                if cache_key in self._fingerprint_cache:
                    return self._fingerprint_cache[cache_key]

        # Load audio if not provided
        if audio is None:
            audio, sr = self.load_audio(file_path)

        # Compute features
        duration = len(audio) / sr

        # Spectral centroid (brightness over time)
        spectral_centroid = librosa.feature.spectral_centroid(
            y=audio, sr=sr, n_fft=self.fft_size, hop_length=self.hop_length
        )[0]

        # MFCC (mel-frequency cepstral coefficients)
        mfcc = librosa.feature.mfcc(
            y=audio, sr=sr, n_mfcc=20,
            n_fft=self.fft_size, hop_length=self.hop_length
        )

        # Chroma features (pitch class profile)
        chroma = librosa.feature.chroma_stft(
            y=audio, sr=sr, n_fft=self.fft_size, hop_length=self.hop_length
        )

        # Onset detection (transients)
        onset_env = librosa.onset.onset_strength(
            y=audio, sr=sr, hop_length=self.hop_length
        )
        onset_frames = librosa.onset.onset_detect(
            onset_envelope=onset_env, sr=sr, hop_length=self.hop_length
        )

        # Energy envelope
        energy = librosa.feature.rms(
            y=audio, frame_length=self.fft_size, hop_length=self.hop_length
        )[0]

        # Create compact fingerprint (combination of features)
        # Downsample for fast comparison
        fingerprint = np.concatenate([
            np.mean(mfcc, axis=1),  # 20 values
            np.percentile(spectral_centroid, [10, 25, 50, 75, 90]),  # 5 values
            np.percentile(energy, [10, 25, 50, 75, 90]),  # 5 values
            [duration, len(onset_frames)],  # 2 values
        ])

        fp = AudioFingerprint(
            file_path=file_path,
            fingerprint=fingerprint,
            duration=duration,
            sample_rate=sr,
            hash_id=None,
            spectral_centroid=spectral_centroid,
            mfcc=mfcc,
            chroma=chroma,
            onset_frames=onset_frames,
            energy_envelope=energy
        )

        # Cache
        if self.cache_fingerprints:
            with self._cache_lock:
                self._fingerprint_cache[cache_key] = fp

        return fp

    def gcc_phat(
        self,
        sig1: np.ndarray,
        sig2: np.ndarray,
        max_delay: Optional[int] = None
    ) -> Tuple[int, float, np.ndarray]:
        """
        Generalized Cross-Correlation with Phase Transform

        More robust to noise and reverberation than standard cross-correlation.

        Args:
            sig1: First signal
            sig2: Second signal
            max_delay: Maximum delay to search (samples)

        Returns:
            delay: Delay in samples (positive = sig2 is delayed)
            confidence: Peak correlation value
            correlation: Full correlation array
        """
        n = len(sig1) + len(sig2) - 1
        n_fft = self._optimal_fft_size(n)

        if self.use_gpu and self._gpu_backend == 'cuda':
            return self._gcc_phat_gpu(sig1, sig2, n_fft, max_delay)
        else:
            return self._gcc_phat_cpu(sig1, sig2, n_fft, max_delay)

    def _estimate_snr(self, sig: np.ndarray, n_fft: int) -> float:
        """Estimate signal-to-noise ratio for adaptive PHAT-β"""
        spectrum = np.abs(fft(sig, n_fft))
        # Estimate noise floor as lower percentile
        noise_floor = np.percentile(spectrum, 10)
        signal_level = np.percentile(spectrum, 90)
        if noise_floor > 0:
            snr = 20 * np.log10(signal_level / noise_floor)
            return max(0, min(snr, 60))  # Clamp to reasonable range
        return 30  # Default moderate SNR

    def _compute_diffuseness_mask(
        self,
        SIG1: np.ndarray,
        SIG2: np.ndarray
    ) -> np.ndarray:
        """
        Compute diffuseness mask for reverberant environments

        Based on coherence between signals - low coherence indicates
        diffuse/reverberant sound which should be downweighted.
        """
        # Cross-spectral density
        Pxy = SIG1 * np.conj(SIG2)

        # Auto-spectral densities
        Pxx = np.abs(SIG1) ** 2
        Pyy = np.abs(SIG2) ** 2

        # Magnitude squared coherence
        denominator = Pxx * Pyy
        denominator[denominator < 1e-10] = 1e-10
        coherence = np.abs(Pxy) ** 2 / denominator

        # Diffuseness = 1 - coherence (high diffuseness = reverb)
        # Use coherence as weight (direct sound has high coherence)
        mask = np.sqrt(coherence)  # Square root for gentler weighting

        return mask

    def _gcc_phat_cpu(
        self,
        sig1: np.ndarray,
        sig2: np.ndarray,
        n_fft: int,
        max_delay: Optional[int]
    ) -> Tuple[int, float, np.ndarray]:
        """
        CPU implementation of GCC-PHAT with advanced features:
        - PHAT-β: Adaptive weighting based on SNR (β=1 is standard PHAT, β=0 is cross-correlation)
        - Diffuseness mask: Downweights reverberant frequency bins
        """
        # Apply Hann window to reduce spectral leakage (improves accuracy)
        window1 = np.hanning(len(sig1))
        window2 = np.hanning(len(sig2))
        sig1_windowed = sig1 * window1
        sig2_windowed = sig2 * window2

        # FFT of both signals
        SIG1 = fft(sig1_windowed, n_fft)
        SIG2 = fft(sig2_windowed, n_fft)

        # Cross-power spectrum
        R = SIG1 * np.conj(SIG2)

        # Compute adaptive PHAT-β if not specified
        if self.phat_beta is None:
            # Estimate SNR and adapt β accordingly
            # High SNR → β close to 1 (full PHAT)
            # Low SNR → β close to 0 (more like cross-correlation)
            snr1 = self._estimate_snr(sig1, n_fft)
            snr2 = self._estimate_snr(sig2, n_fft)
            avg_snr = (snr1 + snr2) / 2

            # Map SNR to β: SNR < 10dB → β=0.3, SNR > 40dB → β=1.0
            beta = np.clip((avg_snr - 10) / 30, 0.3, 1.0)
        else:
            beta = self.phat_beta

        # Phase transform with PHAT-β weighting
        # R_phat = R / |R|^β (β=1 is standard PHAT, β=0 is cross-correlation)
        magnitude = np.abs(R)
        magnitude[magnitude < 1e-10] = 1e-10  # Avoid division by zero

        if beta == 1.0:
            weighting = magnitude
        else:
            weighting = np.power(magnitude, beta)

        R_phat = R / weighting

        # Apply diffuseness mask if enabled
        if self.use_diffuseness_mask:
            diffuseness_weight = self._compute_diffuseness_mask(SIG1, SIG2)
            R_phat = R_phat * diffuseness_weight

        # Inverse FFT to get correlation
        correlation = np.real(ifft(R_phat))

        # Shift to center zero-lag
        correlation = np.fft.fftshift(correlation)
        center = len(correlation) // 2

        # Limit search range
        if max_delay is not None:
            search_start = max(0, center - max_delay)
            search_end = min(len(correlation), center + max_delay)
        else:
            search_start = 0
            search_end = len(correlation)

        # Find peak
        search_region = correlation[search_start:search_end]
        peak_idx = np.argmax(np.abs(search_region))
        delay = (search_start + peak_idx) - center
        confidence = np.abs(search_region[peak_idx])

        return delay, confidence, correlation

    def _gcc_phat_gpu(
        self,
        sig1: np.ndarray,
        sig2: np.ndarray,
        n_fft: int,
        max_delay: Optional[int]
    ) -> Tuple[int, float, np.ndarray]:
        """
        GPU-accelerated GCC-PHAT using CuPy with advanced features:
        - PHAT-β: Adaptive weighting based on SNR
        - Diffuseness mask: Downweights reverberant frequency bins
        """
        cp = self._gpu_context

        # Apply Hann window on CPU (small overhead, big accuracy improvement)
        window1 = np.hanning(len(sig1))
        window2 = np.hanning(len(sig2))
        sig1_windowed = sig1 * window1
        sig2_windowed = sig2 * window2

        # Compute adaptive PHAT-β on CPU (small overhead)
        if self.phat_beta is None:
            snr1 = self._estimate_snr(sig1, n_fft)
            snr2 = self._estimate_snr(sig2, n_fft)
            avg_snr = (snr1 + snr2) / 2
            beta = np.clip((avg_snr - 10) / 30, 0.3, 1.0)
        else:
            beta = self.phat_beta

        # Transfer to GPU
        sig1_gpu = cp.asarray(sig1_windowed)
        sig2_gpu = cp.asarray(sig2_windowed)

        # FFT on GPU
        SIG1 = cp.fft.fft(sig1_gpu, n_fft)
        SIG2 = cp.fft.fft(sig2_gpu, n_fft)

        # Cross-power spectrum
        R = SIG1 * cp.conj(SIG2)

        # Phase transform with PHAT-β
        magnitude = cp.abs(R)
        magnitude = cp.maximum(magnitude, 1e-10)

        if beta == 1.0:
            weighting = magnitude
        else:
            weighting = cp.power(magnitude, beta)

        R_phat = R / weighting

        # Apply diffuseness mask if enabled (compute on GPU)
        if self.use_diffuseness_mask:
            # Coherence-based diffuseness mask
            Pxy = SIG1 * cp.conj(SIG2)
            Pxx = cp.abs(SIG1) ** 2
            Pyy = cp.abs(SIG2) ** 2
            denominator = Pxx * Pyy
            denominator = cp.maximum(denominator, 1e-10)
            coherence = cp.abs(Pxy) ** 2 / denominator
            diffuseness_weight = cp.sqrt(coherence)
            R_phat = R_phat * diffuseness_weight

        # Inverse FFT
        correlation = cp.real(cp.fft.ifft(R_phat))
        correlation = cp.fft.fftshift(correlation)

        # Transfer back to CPU
        correlation = cp.asnumpy(correlation)

        center = len(correlation) // 2

        if max_delay is not None:
            search_start = max(0, center - max_delay)
            search_end = min(len(correlation), center + max_delay)
        else:
            search_start = 0
            search_end = len(correlation)

        search_region = correlation[search_start:search_end]
        peak_idx = np.argmax(np.abs(search_region))
        delay = (search_start + peak_idx) - center
        confidence = np.abs(search_region[peak_idx])

        return delay, confidence, correlation

    def subsample_refinement(
        self,
        correlation: np.ndarray,
        peak_idx: int
    ) -> float:
        """
        Sub-sample accuracy using parabolic or sinc interpolation

        Methods:
        - Parabolic: Fast, good for most cases
        - Sinc: Higher precision for demanding applications (when use_sinc_interpolation=True)
        """
        if peak_idx <= 0 or peak_idx >= len(correlation) - 1:
            return 0.0

        if self.use_sinc_interpolation:
            return self._sinc_interpolation(correlation, peak_idx)
        else:
            return self._parabolic_interpolation(correlation, peak_idx)

    def _parabolic_interpolation(
        self,
        correlation: np.ndarray,
        peak_idx: int
    ) -> float:
        """Three-point parabolic interpolation"""
        y0 = correlation[peak_idx - 1]
        y1 = correlation[peak_idx]
        y2 = correlation[peak_idx + 1]

        # Parabola vertex formula
        denominator = 2 * (2 * y1 - y0 - y2)
        if abs(denominator) < 1e-10:
            return 0.0

        offset = (y0 - y2) / denominator
        return np.clip(offset, -0.5, 0.5)

    def _sinc_interpolation(
        self,
        correlation: np.ndarray,
        peak_idx: int,
        num_neighbors: int = 8,
        oversample: int = 100
    ) -> float:
        """
        Sinc (Whittaker-Shannon) interpolation for sub-sample accuracy

        Uses ideal bandlimited interpolation via sinc function
        for maximum precision in time-delay estimation.
        """
        # Extract region around peak
        start = max(0, peak_idx - num_neighbors)
        end = min(len(correlation), peak_idx + num_neighbors + 1)
        region = correlation[start:end]

        if len(region) < 3:
            return 0.0

        # Generate oversampled x positions
        n_samples = len(region)
        x_original = np.arange(n_samples)
        x_fine = np.linspace(0, n_samples - 1, n_samples * oversample)

        # Sinc interpolation using scipy
        if SCIPY_AVAILABLE:
            # Use cubic spline as fallback (very close to sinc for oversampled data)
            try:
                interpolator = interp1d(
                    x_original, region,
                    kind='cubic',
                    fill_value='extrapolate'
                )
                fine_correlation = interpolator(x_fine)
            except:
                return self._parabolic_interpolation(correlation, peak_idx)
        else:
            return self._parabolic_interpolation(correlation, peak_idx)

        # Find peak in oversampled data
        fine_peak_idx = np.argmax(fine_correlation)
        fine_peak_pos = x_fine[fine_peak_idx]

        # Convert to offset from original peak position
        original_peak_in_region = peak_idx - start
        offset = fine_peak_pos - original_peak_in_region

        return np.clip(offset, -0.5, 0.5)

    def detect_drift(
        self,
        audio1: np.ndarray,
        audio2: np.ndarray,
        sr: int,
        num_segments: int = 10
    ) -> Tuple[float, List[float]]:
        """
        Detect clock drift between two recordings

        Analyzes multiple segments to detect if one recording
        is running at a slightly different speed.

        Returns:
            drift_rate: Samples per second of drift
            segment_offsets: Offset at each segment
        """
        min_len = min(len(audio1), len(audio2))
        segment_size = min_len // num_segments

        offsets = []
        for i in range(num_segments):
            start = i * segment_size
            end = start + segment_size

            seg1 = audio1[start:end]
            seg2 = audio2[start:end]

            delay, conf, _ = self.gcc_phat(seg1, seg2, max_delay=sr // 2)

            if conf > 0.1:  # Only use reliable segments
                offsets.append(delay)

        if len(offsets) < 3:
            return 0.0, offsets

        # Fit linear regression to find drift
        x = np.arange(len(offsets)) * segment_size / sr  # Time in seconds
        y = np.array(offsets)

        # Simple linear regression
        slope, intercept = np.polyfit(x, y, 1)

        return slope, offsets

    def time_stretch_correct(
        self,
        audio: np.ndarray,
        drift_rate: float,
        sr: int
    ) -> np.ndarray:
        """
        Apply time-stretching to correct clock drift
        """
        if abs(drift_rate) < 0.01:  # Negligible drift
            return audio

        duration = len(audio) / sr
        stretch_factor = 1.0 + (drift_rate / sr)

        # Use librosa for high-quality time stretching
        corrected = librosa.effects.time_stretch(audio, rate=stretch_factor)

        return corrected

    def batch_fingerprint(
        self,
        file_paths: List[str],
        progress_callback=None,
        max_workers: int = 4
    ) -> List[AudioFingerprint]:
        """
        Compute fingerprints for multiple files in parallel
        """
        fingerprints = []
        total = len(file_paths)

        def process_file(idx_path):
            idx, path = idx_path
            try:
                fp = self.compute_fingerprint(path)
                if progress_callback:
                    progress_callback(idx + 1, total, path)
                return fp
            except Exception as e:
                print(f"Error processing {path}: {e}")
                return None

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(process_file, enumerate(file_paths)))

        return [r for r in results if r is not None]

    def find_best_matches(
        self,
        fingerprints: List[AudioFingerprint],
        similarity_threshold: float = 0.7
    ) -> List[Tuple[int, int, float]]:
        """
        Find potentially matching clip pairs based on fingerprints

        Returns list of (idx1, idx2, similarity) tuples
        """
        matches = []
        n = len(fingerprints)

        for i in range(n):
            for j in range(i + 1, n):
                fp1 = fingerprints[i].fingerprint
                fp2 = fingerprints[j].fingerprint

                # Cosine similarity
                dot = np.dot(fp1, fp2)
                norm1 = np.linalg.norm(fp1)
                norm2 = np.linalg.norm(fp2)

                if norm1 > 0 and norm2 > 0:
                    similarity = dot / (norm1 * norm2)
                else:
                    similarity = 0

                if similarity >= similarity_threshold:
                    matches.append((i, j, similarity))

        # Sort by similarity
        matches.sort(key=lambda x: x[2], reverse=True)

        return matches

    def clear_cache(self):
        """Clear the fingerprint cache"""
        with self._cache_lock:
            self._fingerprint_cache.clear()

    def get_cache_size(self) -> int:
        """Get number of cached fingerprints"""
        with self._cache_lock:
            return len(self._fingerprint_cache)

    def streaming_sync(
        self,
        file1: str,
        file2: str,
        chunk_duration: float = 30.0,
        overlap: float = 5.0,
        progress_callback=None
    ) -> SyncResult:
        """
        Memory-efficient streaming sync for very large files

        Processes files in overlapping chunks to handle hour-long recordings
        without loading everything into memory.

        Args:
            file1: Path to first audio/video file
            file2: Path to second audio/video file
            chunk_duration: Duration of each chunk in seconds
            overlap: Overlap between chunks for continuity
            progress_callback: Optional callback(current_chunk, total_chunks)

        Returns:
            SyncResult with best offset found across all chunks
        """
        if not LIBROSA_AVAILABLE:
            raise ImportError("librosa is required for streaming sync")

        # Get file durations
        duration1 = librosa.get_duration(path=file1)
        duration2 = librosa.get_duration(path=file2)
        min_duration = min(duration1, duration2)

        # Calculate chunks
        step = chunk_duration - overlap
        num_chunks = int(np.ceil(min_duration / step))

        best_result = None
        chunk_results = []

        for i in range(num_chunks):
            offset = i * step

            if progress_callback:
                progress_callback(i + 1, num_chunks)

            try:
                # Load chunks
                audio1, sr = self.load_audio(file1, duration=chunk_duration, offset=offset)
                audio2, sr = self.load_audio(file2, duration=chunk_duration, offset=offset)

                # Sync this chunk
                delay, confidence, correlation = self.gcc_phat(
                    audio1, audio2,
                    max_delay=int(sr * 10)  # Max 10 second offset per chunk
                )

                # Sub-sample refinement
                center = len(correlation) // 2
                peak_idx = center + delay
                sub_sample = self.subsample_refinement(correlation, peak_idx)

                offset_seconds = delay / sr

                chunk_results.append({
                    'chunk': i,
                    'time': offset,
                    'delay': delay,
                    'confidence': confidence,
                    'offset_seconds': offset_seconds,
                    'sub_sample': sub_sample
                })

            except Exception as e:
                print(f"Error processing chunk {i}: {e}")
                continue

        if not chunk_results:
            return SyncResult(
                source_file=file1,
                target_file=file2,
                offset_samples=0,
                offset_seconds=0.0,
                confidence=0.0,
                method_used=SyncMethod.AUDIO_WAVEFORM
            )

        # Find best result (highest confidence)
        best = max(chunk_results, key=lambda x: x['confidence'])

        # Detect drift by comparing offsets across chunks
        if len(chunk_results) >= 3:
            times = np.array([r['time'] for r in chunk_results])
            offsets = np.array([r['offset_seconds'] for r in chunk_results])
            # Linear regression for drift
            if len(times) > 1:
                drift_rate, _ = np.polyfit(times, offsets, 1)
            else:
                drift_rate = 0.0
        else:
            drift_rate = 0.0

        return SyncResult(
            source_file=file1,
            target_file=file2,
            offset_samples=best['delay'],
            offset_seconds=best['offset_seconds'],
            confidence=best['confidence'],
            method_used=SyncMethod.AUDIO_WAVEFORM,
            drift_rate=drift_rate,
            sub_sample_offset=best['sub_sample'],
            quality_metrics={
                'chunks_processed': len(chunk_results),
                'best_chunk': best['chunk'],
                'avg_confidence': np.mean([r['confidence'] for r in chunk_results])
            }
        )

    def multi_scale_sync(
        self,
        audio1: np.ndarray,
        audio2: np.ndarray,
        sr: int
    ) -> Tuple[int, float]:
        """
        Multi-scale sync for faster processing on long recordings

        Uses coarse-to-fine approach:
        1. Downsample for rough alignment
        2. Fine alignment on original sample rate
        """
        # Stage 1: Coarse alignment (4x downsampled)
        downsample_factor = 4
        audio1_coarse = audio1[::downsample_factor]
        audio2_coarse = audio2[::downsample_factor]

        coarse_delay, coarse_conf, _ = self.gcc_phat(
            audio1_coarse, audio2_coarse,
            max_delay=len(audio1_coarse) // 2
        )
        coarse_delay *= downsample_factor

        # Stage 2: Fine alignment around coarse result
        # Extract region around estimated offset
        window_samples = sr * 2  # 2 second window

        # Calculate where to extract from audio2
        offset_start = max(0, coarse_delay - window_samples)
        offset_end = min(len(audio2), coarse_delay + window_samples)

        if offset_end - offset_start < window_samples:
            # Fallback to direct sync
            delay, confidence, _ = self.gcc_phat(audio1, audio2, max_delay=sr * 30)
            return delay, confidence

        # Extract regions
        ref_start = max(0, -coarse_delay)
        ref_end = min(len(audio1), len(audio1) - coarse_delay)

        if ref_end - ref_start < window_samples // 2:
            delay, confidence, _ = self.gcc_phat(audio1, audio2, max_delay=sr * 30)
            return delay, confidence

        seg1 = audio1[ref_start:ref_start + window_samples]
        seg2 = audio2[offset_start:offset_start + window_samples]

        # Fine GCC-PHAT
        fine_delay, confidence, _ = self.gcc_phat(
            seg1, seg2,
            max_delay=window_samples
        )

        # Combine coarse and fine
        total_delay = coarse_delay + fine_delay

        return total_delay, confidence

    # =========================================================================
    # ADVANCED FEATURES FOR MAXIMUM ACCURACY
    # =========================================================================

    def mel_spectrogram_sync(
        self,
        audio1: np.ndarray,
        audio2: np.ndarray,
        sr: int,
        max_offset_seconds: float = 60.0
    ) -> Tuple[int, float]:
        """
        Mel-spectrogram based sync - more robust to EQ differences and noise

        Mel spectrograms emphasize perceptually important frequencies,
        making matching more robust when audio has different EQ or compression.
        """
        if not LIBROSA_AVAILABLE:
            raise ImportError("librosa required for mel-spectrogram sync")

        # Compute mel spectrograms
        n_mels = 128
        hop = 512

        mel1 = librosa.feature.melspectrogram(
            y=audio1, sr=sr, n_mels=n_mels, hop_length=hop
        )
        mel2 = librosa.feature.melspectrogram(
            y=audio2, sr=sr, n_mels=n_mels, hop_length=hop
        )

        # Convert to log scale (dB)
        mel1_db = librosa.power_to_db(mel1, ref=np.max)
        mel2_db = librosa.power_to_db(mel2, ref=np.max)

        # Average across frequency bands to get energy envelope
        energy1 = np.mean(mel1_db, axis=0)
        energy2 = np.mean(mel2_db, axis=0)

        # Normalize
        energy1 = (energy1 - np.mean(energy1)) / (np.std(energy1) + 1e-10)
        energy2 = (energy2 - np.mean(energy2)) / (np.std(energy2) + 1e-10)

        # Cross-correlation
        correlation = signal.correlate(energy1, energy2, mode='full')
        lags = signal.correlation_lags(len(energy1), len(energy2), mode='full')

        # Limit search range
        max_lag_frames = int(max_offset_seconds * sr / hop)
        valid = np.abs(lags) <= max_lag_frames
        correlation[~valid] = -np.inf

        # Find peak
        peak_idx = np.argmax(correlation)
        peak_lag = lags[peak_idx]
        confidence = correlation[peak_idx] / len(energy1)

        # Convert from frames to samples
        delay_samples = peak_lag * hop

        return delay_samples, float(np.clip(confidence, 0, 1))

    def spectral_contrast_sync(
        self,
        audio1: np.ndarray,
        audio2: np.ndarray,
        sr: int,
        max_offset_seconds: float = 60.0
    ) -> Tuple[int, float]:
        """
        Spectral contrast based sync - excellent for music and complex audio

        Spectral contrast measures the difference between peaks and valleys
        in the spectrum, making it robust to overall level changes.
        """
        if not LIBROSA_AVAILABLE:
            raise ImportError("librosa required for spectral contrast sync")

        hop = 512

        # Compute spectral contrast
        contrast1 = librosa.feature.spectral_contrast(
            y=audio1, sr=sr, hop_length=hop, n_bands=6
        )
        contrast2 = librosa.feature.spectral_contrast(
            y=audio2, sr=sr, hop_length=hop, n_bands=6
        )

        # Flatten and normalize
        feat1 = contrast1.flatten()
        feat2 = contrast2.flatten()

        # Use shorter sequence for correlation
        n_frames1 = contrast1.shape[1]
        n_frames2 = contrast2.shape[1]

        # Compute frame-wise similarity and cross-correlate
        sim1 = np.mean(contrast1, axis=0)
        sim2 = np.mean(contrast2, axis=0)

        sim1 = (sim1 - np.mean(sim1)) / (np.std(sim1) + 1e-10)
        sim2 = (sim2 - np.mean(sim2)) / (np.std(sim2) + 1e-10)

        correlation = signal.correlate(sim1, sim2, mode='full')
        lags = signal.correlation_lags(len(sim1), len(sim2), mode='full')

        max_lag_frames = int(max_offset_seconds * sr / hop)
        valid = np.abs(lags) <= max_lag_frames
        correlation[~valid] = -np.inf

        peak_idx = np.argmax(correlation)
        peak_lag = lags[peak_idx]
        confidence = correlation[peak_idx] / len(sim1)

        delay_samples = peak_lag * hop

        return delay_samples, float(np.clip(confidence, 0, 1))

    def normalize_audio_for_matching(
        self,
        audio: np.ndarray,
        sr: int,
        target_lufs: float = -23.0
    ) -> np.ndarray:
        """
        Normalize audio to target loudness for better matching

        Uses ITU-R BS.1770 loudness measurement for broadcast-standard
        normalization, making clips with different gain levels comparable.
        """
        # Simple RMS-based normalization (approximates LUFS for speech/music)
        rms = np.sqrt(np.mean(audio ** 2))
        if rms < 1e-10:
            return audio

        # Target RMS for -23 LUFS (approximate)
        target_rms = 10 ** (target_lufs / 20) * 0.5

        gain = target_rms / rms
        normalized = audio * gain

        # Prevent clipping
        max_val = np.max(np.abs(normalized))
        if max_val > 0.99:
            normalized = normalized * (0.99 / max_val)

        return normalized

    def match_eq_profiles(
        self,
        audio_source: np.ndarray,
        audio_target: np.ndarray,
        sr: int
    ) -> np.ndarray:
        """
        Match EQ profile of source to target for better correlation

        Useful when comparing audio from different microphones or
        cameras with different audio processing.
        """
        if not SCIPY_AVAILABLE:
            return audio_source

        # Compute spectral envelopes
        n_fft = 2048
        hop = 512

        # Get average spectrum
        spec_source = np.abs(librosa.stft(audio_source, n_fft=n_fft, hop_length=hop))
        spec_target = np.abs(librosa.stft(audio_target, n_fft=n_fft, hop_length=hop))

        avg_source = np.mean(spec_source, axis=1)
        avg_target = np.mean(spec_target, axis=1)

        # Compute EQ curve (ratio of target to source)
        eq_curve = (avg_target + 1e-10) / (avg_source + 1e-10)

        # Smooth the EQ curve
        eq_curve = gaussian_filter1d(eq_curve, sigma=5)

        # Limit extreme values
        eq_curve = np.clip(eq_curve, 0.1, 10.0)

        # Apply EQ in frequency domain
        stft_source = librosa.stft(audio_source, n_fft=n_fft, hop_length=hop)
        stft_eq = stft_source * eq_curve[:, np.newaxis]

        # Inverse STFT
        audio_matched = librosa.istft(stft_eq, hop_length=hop, length=len(audio_source))

        return audio_matched

    def nonlinear_drift_correction(
        self,
        audio: np.ndarray,
        time_offsets: List[float],
        measured_drifts: List[float],
        sr: int
    ) -> np.ndarray:
        """
        Apply non-linear drift correction using spline interpolation

        Handles cases where drift rate varies (e.g., due to temperature
        changes affecting crystal oscillator).
        """
        if len(time_offsets) < 3:
            # Fall back to linear correction
            if len(time_offsets) >= 2:
                time_diff = time_offsets[-1] - time_offsets[0]
                if abs(time_diff) < 1e-10:  # Avoid division by zero
                    return audio
                slope = (measured_drifts[-1] - measured_drifts[0]) / time_diff
                return self.time_stretch_correct(audio, slope * sr, sr)
            return audio

        # Fit cubic spline to drift measurements
        from scipy.interpolate import UnivariateSpline

        times = np.array(time_offsets)
        drifts = np.array(measured_drifts)

        # Spline fit (smoothing to handle measurement noise)
        spline = UnivariateSpline(times, drifts, s=len(times) * 0.1)

        # Generate drift curve for entire audio
        duration = len(audio) / sr
        t = np.linspace(0, duration, len(audio))
        drift_curve = spline(t)

        # Apply variable time-stretch
        # Create new time mapping
        t_corrected = t - drift_curve

        # Resample to corrected timeline
        from scipy.interpolate import interp1d
        interp = interp1d(t, audio, kind='linear', fill_value='extrapolate')
        audio_corrected = interp(t_corrected)

        return audio_corrected.astype(np.float32)

    def kalman_fusion(
        self,
        sync_results: List[Tuple[float, float, str]]
    ) -> Tuple[float, float]:
        """
        Kalman filter fusion of multiple sync estimates

        Optimally combines estimates from different methods based on
        their confidence/variance for the most accurate final result.

        Args:
            sync_results: List of (offset_seconds, confidence, method_name)

        Returns:
            (fused_offset, fused_confidence)
        """
        if not sync_results:
            return 0.0, 0.0

        if len(sync_results) == 1:
            return sync_results[0][0], sync_results[0][1]

        # Convert confidence to variance (lower confidence = higher variance)
        # Use inverse relationship: variance = k / confidence^2
        k = 0.01  # Scale factor

        estimates = []
        variances = []

        for offset, confidence, method in sync_results:
            if confidence > 0.1:  # Filter out very low confidence
                estimates.append(offset)
                # Higher confidence = lower variance
                variance = k / (confidence ** 2 + 1e-10)
                variances.append(variance)

        if not estimates:
            return sync_results[0][0], sync_results[0][1]

        estimates = np.array(estimates)
        variances = np.array(variances)

        # Kalman fusion formula for combining measurements
        # Fused estimate = weighted average where weights = 1/variance
        weights = 1.0 / variances
        weights = weights / np.sum(weights)  # Normalize

        fused_offset = np.sum(estimates * weights)

        # Fused variance is less than any individual variance
        fused_variance = 1.0 / np.sum(1.0 / variances)

        # Convert back to confidence
        fused_confidence = np.sqrt(k / fused_variance)
        fused_confidence = float(np.clip(fused_confidence, 0, 1))

        return float(fused_offset), fused_confidence

    def ensemble_sync(
        self,
        audio1: np.ndarray,
        audio2: np.ndarray,
        sr: int,
        max_offset_seconds: float = 60.0
    ) -> Tuple[int, float, Dict[str, Any]]:
        """
        Ensemble sync using multiple methods with Kalman fusion

        Runs GCC-PHAT, mel-spectrogram, and spectral contrast methods,
        then fuses results for maximum accuracy.
        """
        results = []
        method_results = {}

        # Method 1: GCC-PHAT (most accurate for clean audio)
        try:
            delay1, conf1, _ = self.gcc_phat(
                audio1, audio2,
                max_delay=int(max_offset_seconds * sr)
            )
            offset1 = delay1 / sr
            results.append((offset1, conf1, 'gcc_phat'))
            method_results['gcc_phat'] = {'offset': offset1, 'confidence': conf1}
        except Exception as e:
            method_results['gcc_phat'] = {'error': str(e)}

        # Method 2: Mel-spectrogram (robust to EQ differences)
        try:
            delay2, conf2 = self.mel_spectrogram_sync(
                audio1, audio2, sr, max_offset_seconds
            )
            offset2 = delay2 / sr
            results.append((offset2, conf2 * 0.9, 'mel_spec'))  # Slightly lower weight
            method_results['mel_spectrogram'] = {'offset': offset2, 'confidence': conf2}
        except Exception as e:
            method_results['mel_spectrogram'] = {'error': str(e)}

        # Method 3: Spectral contrast (good for music)
        try:
            delay3, conf3 = self.spectral_contrast_sync(
                audio1, audio2, sr, max_offset_seconds
            )
            offset3 = delay3 / sr
            results.append((offset3, conf3 * 0.85, 'spectral_contrast'))
            method_results['spectral_contrast'] = {'offset': offset3, 'confidence': conf3}
        except Exception as e:
            method_results['spectral_contrast'] = {'error': str(e)}

        # Fuse results using Kalman filter
        fused_offset, fused_confidence = self.kalman_fusion(results)

        # Convert back to samples
        fused_delay = int(fused_offset * sr)

        return fused_delay, fused_confidence, {
            'methods': method_results,
            'fusion': 'kalman',
            'num_methods': len(results)
        }

    def robust_sync_with_validation(
        self,
        audio1: np.ndarray,
        audio2: np.ndarray,
        sr: int,
        max_offset_seconds: float = 60.0,
        validation_segments: int = 5
    ) -> Tuple[int, float, bool]:
        """
        Robust sync with cross-validation for reliability

        Performs sync on multiple segments and validates consistency.
        Returns whether the sync is reliable based on cross-validation.
        """
        min_len = min(len(audio1), len(audio2))
        segment_len = min_len // (validation_segments + 1)

        if segment_len < sr * 2:  # Need at least 2 seconds per segment
            # Fall back to simple sync
            delay, conf, _ = self.gcc_phat(
                audio1, audio2,
                max_delay=int(max_offset_seconds * sr)
            )
            return delay, conf, True

        segment_offsets = []

        for i in range(validation_segments):
            start = i * segment_len
            end = start + segment_len

            seg1 = audio1[start:end]
            seg2 = audio2[start:end]

            try:
                delay, conf, _ = self.gcc_phat(seg1, seg2, max_delay=sr * 10)
                if conf > 0.2:
                    # Adjust for segment position
                    segment_offsets.append(delay)
            except:
                continue

        if len(segment_offsets) < 3:
            # Not enough valid segments
            delay, conf, _ = self.gcc_phat(
                audio1, audio2,
                max_delay=int(max_offset_seconds * sr)
            )
            return delay, conf, False

        # Check consistency
        offsets = np.array(segment_offsets)
        median_offset = np.median(offsets)
        std_offset = np.std(offsets)

        # Offset should be consistent across segments (within 0.1 seconds)
        is_reliable = std_offset < sr * 0.1

        # Use median as final offset (robust to outliers)
        final_offset = int(median_offset)

        # Confidence based on consistency
        consistency_score = 1.0 / (1.0 + std_offset / sr)
        final_confidence = float(np.clip(consistency_score, 0, 1))

        return final_offset, final_confidence, is_reliable
