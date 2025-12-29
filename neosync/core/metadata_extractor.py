"""
Metadata & Timecode Extraction
==============================

Extract sync-relevant metadata from media files:
- Embedded timecode (LTC, VITC)
- Creation timestamps
- Camera metadata
- GPS coordinates
- Audio sample rate / frame rate
"""

import os
import re
import json
import subprocess
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path


@dataclass
class Timecode:
    """SMPTE Timecode representation"""
    hours: int = 0
    minutes: int = 0
    seconds: int = 0
    frames: int = 0
    fps: float = 24.0
    drop_frame: bool = False

    @classmethod
    def from_string(cls, tc_string: str, fps: float = 24.0) -> 'Timecode':
        """Parse timecode string like '01:23:45:12' or '01:23:45;12' (drop frame)"""
        drop_frame = ';' in tc_string
        parts = re.split(r'[:;]', tc_string)
        if len(parts) >= 4:
            return cls(
                hours=int(parts[0]),
                minutes=int(parts[1]),
                seconds=int(parts[2]),
                frames=int(parts[3]),
                fps=fps,
                drop_frame=drop_frame
            )
        return cls(fps=fps)

    @classmethod
    def from_frames(cls, total_frames: int, fps: float = 24.0) -> 'Timecode':
        """Create timecode from total frame count"""
        frames_per_second = int(fps)
        frames = total_frames % frames_per_second
        total_seconds = total_frames // frames_per_second
        seconds = total_seconds % 60
        total_minutes = total_seconds // 60
        minutes = total_minutes % 60
        hours = total_minutes // 60
        return cls(hours, minutes, seconds, frames, fps)

    def to_frames(self) -> int:
        """Convert to total frame count"""
        frames_per_second = int(self.fps)
        return (
            self.frames +
            self.seconds * frames_per_second +
            self.minutes * 60 * frames_per_second +
            self.hours * 3600 * frames_per_second
        )

    def to_seconds(self) -> float:
        """Convert to seconds"""
        return self.to_frames() / self.fps

    def __str__(self) -> str:
        sep = ';' if self.drop_frame else ':'
        return f"{self.hours:02d}:{self.minutes:02d}:{self.seconds:02d}{sep}{self.frames:02d}"

    def __sub__(self, other: 'Timecode') -> 'Timecode':
        """Subtract timecodes to get difference"""
        diff_frames = self.to_frames() - other.to_frames()
        return Timecode.from_frames(abs(diff_frames), self.fps)


@dataclass
class GPSCoordinates:
    """GPS location data"""
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    timestamp: Optional[datetime] = None


@dataclass
class MediaMetadata:
    """Comprehensive media metadata"""
    file_path: str
    file_name: str
    file_size: int

    # Duration and timing
    duration_seconds: float = 0.0
    frame_count: int = 0
    fps: float = 24.0
    sample_rate: int = 48000

    # Timecode
    start_timecode: Optional[Timecode] = None
    timecode_source: Optional[str] = None  # 'embedded', 'filename', 'creation_time'

    # Timestamps
    creation_time: Optional[datetime] = None
    modification_time: Optional[datetime] = None
    recording_time: Optional[datetime] = None

    # Video properties
    video_codec: Optional[str] = None
    video_bitrate: Optional[int] = None
    width: int = 0
    height: int = 0

    # Audio properties
    audio_codec: Optional[str] = None
    audio_channels: int = 0
    audio_bitrate: Optional[int] = None
    has_audio: bool = False

    # Camera metadata
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    camera_serial: Optional[str] = None
    lens_info: Optional[str] = None

    # GPS
    gps: Optional[GPSCoordinates] = None

    # Raw metadata
    raw_metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def camera_id(self) -> str:
        """Generate unique camera identifier"""
        parts = []
        if self.camera_make:
            parts.append(self.camera_make)
        if self.camera_model:
            parts.append(self.camera_model)
        if self.camera_serial:
            parts.append(self.camera_serial)
        return "_".join(parts) if parts else "Unknown"


class MetadataExtractor:
    """
    Extract metadata from media files using ffprobe and exiftool
    """

    def __init__(self):
        self.ffprobe_path = self._find_executable('ffprobe')
        self.exiftool_path = self._find_executable('exiftool')
        self._cache: Dict[str, MediaMetadata] = {}

    def _find_executable(self, name: str) -> Optional[str]:
        """Find executable in PATH"""
        import shutil
        return shutil.which(name)

    def _check_audio_fallback(self, file_path: str) -> bool:
        """Fallback audio detection using librosa if ffprobe fails"""
        try:
            import librosa
            # Try to load just a tiny bit of audio to check if it exists
            y, sr = librosa.load(file_path, sr=None, mono=True, duration=0.1)
            has_audio = len(y) > 0
            if has_audio:
                print(f"[INFO] Fallback audio detection: found audio in {Path(file_path).name}")
            return has_audio
        except Exception as e:
            # If librosa can't load audio, there probably isn't any
            print(f"[DEBUG] No audio detected in {Path(file_path).name}: {e}")
            return False

    def extract(self, file_path: str, use_cache: bool = True) -> MediaMetadata:
        """
        Extract all metadata from media file
        """
        file_path = str(Path(file_path).resolve())

        if use_cache and file_path in self._cache:
            return self._cache[file_path]

        # Basic file info
        path = Path(file_path)
        metadata = MediaMetadata(
            file_path=file_path,
            file_name=path.name,
            file_size=path.stat().st_size if path.exists() else 0,
            modification_time=datetime.fromtimestamp(path.stat().st_mtime) if path.exists() else None
        )

        # Extract with ffprobe (primary source)
        if self.ffprobe_path:
            self._extract_ffprobe(metadata)
        else:
            print("[WARNING] ffprobe not found - audio detection may fail")

        # Fallback audio detection if ffprobe didn't detect audio
        if not metadata.has_audio:
            metadata.has_audio = self._check_audio_fallback(file_path)

        # Extract with exiftool (additional metadata)
        if self.exiftool_path:
            self._extract_exiftool(metadata)

        # Try to parse timecode from filename
        if metadata.start_timecode is None:
            tc = self._parse_timecode_from_filename(path.name)
            if tc:
                metadata.start_timecode = tc
                metadata.timecode_source = 'filename'

        # Cache result
        self._cache[file_path] = metadata

        return metadata

    def _extract_ffprobe(self, metadata: MediaMetadata):
        """Extract metadata using ffprobe"""
        try:
            cmd = [
                self.ffprobe_path,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                metadata.file_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                print(f"ffprobe failed for {metadata.file_path}: {result.stderr}")
                return

            data = json.loads(result.stdout)

            # Format info
            fmt = data.get('format', {})
            metadata.duration_seconds = float(fmt.get('duration', 0))
            metadata.raw_metadata['ffprobe'] = data

            # Parse streams
            for stream in data.get('streams', []):
                codec_type = stream.get('codec_type')

                if codec_type == 'video':
                    metadata.video_codec = stream.get('codec_name')
                    metadata.width = stream.get('width', 0)
                    metadata.height = stream.get('height', 0)
                    metadata.video_bitrate = int(stream.get('bit_rate', 0) or 0)

                    # Frame rate
                    fps_str = stream.get('r_frame_rate', '24/1')
                    if '/' in fps_str:
                        num, den = map(int, fps_str.split('/'))
                        metadata.fps = num / den if den > 0 else 24.0
                    else:
                        metadata.fps = float(fps_str)

                    metadata.frame_count = int(stream.get('nb_frames', 0) or 0)
                    if metadata.frame_count == 0 and metadata.duration_seconds > 0:
                        metadata.frame_count = int(metadata.duration_seconds * metadata.fps)

                    # Timecode from tags
                    tags = stream.get('tags', {})
                    tc_str = tags.get('timecode') or tags.get('TIMECODE')
                    if tc_str:
                        metadata.start_timecode = Timecode.from_string(tc_str, metadata.fps)
                        metadata.timecode_source = 'embedded'

                elif codec_type == 'audio':
                    metadata.has_audio = True
                    metadata.audio_codec = stream.get('codec_name')
                    metadata.audio_channels = stream.get('channels', 0)
                    metadata.sample_rate = int(stream.get('sample_rate', 48000))
                    metadata.audio_bitrate = int(stream.get('bit_rate', 0) or 0)

            # Format tags
            tags = fmt.get('tags', {})

            # Creation time
            creation_str = tags.get('creation_time') or tags.get('date')
            if creation_str:
                try:
                    metadata.creation_time = datetime.fromisoformat(
                        creation_str.replace('Z', '+00:00')
                    )
                    metadata.recording_time = metadata.creation_time
                except:
                    pass

            # Camera make/model from format tags
            if 'com.apple.quicktime.make' in tags:
                metadata.camera_make = tags['com.apple.quicktime.make']
            if 'com.apple.quicktime.model' in tags:
                metadata.camera_model = tags['com.apple.quicktime.model']

        except Exception as e:
            print(f"ffprobe error for {metadata.file_path}: {e}")

    def _extract_exiftool(self, metadata: MediaMetadata):
        """Extract additional metadata using exiftool"""
        try:
            cmd = [
                self.exiftool_path,
                '-json',
                '-n',  # Numeric output
                '-GPS*',
                '-Make',
                '-Model',
                '-SerialNumber',
                '-LensModel',
                '-DateTimeOriginal',
                '-CreateDate',
                '-TimeCode',
                metadata.file_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            data = json.loads(result.stdout)[0]

            metadata.raw_metadata['exiftool'] = data

            # Camera info
            if 'Make' in data:
                metadata.camera_make = data['Make']
            if 'Model' in data:
                metadata.camera_model = data['Model']
            if 'SerialNumber' in data:
                metadata.camera_serial = data['SerialNumber']
            if 'LensModel' in data:
                metadata.lens_info = data['LensModel']

            # GPS
            if 'GPSLatitude' in data and 'GPSLongitude' in data:
                metadata.gps = GPSCoordinates(
                    latitude=float(data['GPSLatitude']),
                    longitude=float(data['GPSLongitude']),
                    altitude=float(data.get('GPSAltitude', 0))
                )

            # Recording time
            date_str = data.get('DateTimeOriginal') or data.get('CreateDate')
            if date_str and metadata.recording_time is None:
                try:
                    metadata.recording_time = datetime.strptime(
                        date_str, '%Y:%m:%d %H:%M:%S'
                    )
                except:
                    pass

            # Timecode from exiftool
            if 'TimeCode' in data and metadata.start_timecode is None:
                metadata.start_timecode = Timecode.from_string(
                    str(data['TimeCode']), metadata.fps
                )
                metadata.timecode_source = 'embedded'

        except Exception as e:
            # exiftool might not be installed, that's okay
            pass

    def _parse_timecode_from_filename(self, filename: str) -> Optional[Timecode]:
        """
        Try to extract timecode from filename patterns

        Common patterns:
        - CLIP_01_23_45_12.mov (HH_MM_SS_FF)
        - 01-23-45-12_clip.mp4
        - TC01234512.mxf
        """
        patterns = [
            r'(\d{2})[_\-:](\d{2})[_\-:](\d{2})[_\-:](\d{2})',  # 01_23_45_12 or 01:23:45:12
            r'TC(\d{2})(\d{2})(\d{2})(\d{2})',  # TC01234512
        ]

        for pattern in patterns:
            match = re.search(pattern, filename)
            if match:
                h, m, s, f = map(int, match.groups())
                if h < 24 and m < 60 and s < 60 and f < 60:
                    return Timecode(h, m, s, f)

        return None

    def group_by_camera(
        self,
        metadata_list: List[MediaMetadata]
    ) -> Dict[str, List[MediaMetadata]]:
        """Group media files by camera"""
        groups: Dict[str, List[MediaMetadata]] = {}

        for meta in metadata_list:
            camera_id = meta.camera_id
            if camera_id not in groups:
                groups[camera_id] = []
            groups[camera_id].append(meta)

        # Sort each group by recording time
        for camera_id in groups:
            groups[camera_id].sort(
                key=lambda m: m.recording_time or m.creation_time or datetime.min
            )

        return groups

    def find_timecode_sync_pairs(
        self,
        metadata_list: List[MediaMetadata],
        max_offset_seconds: float = 1.0
    ) -> List[Tuple[int, int, float]]:
        """
        Find clip pairs that can be synced via timecode

        Returns list of (idx1, idx2, offset_seconds)
        """
        pairs = []
        n = len(metadata_list)

        for i in range(n):
            if metadata_list[i].start_timecode is None:
                continue

            for j in range(i + 1, n):
                if metadata_list[j].start_timecode is None:
                    continue

                # Calculate offset between timecodes
                tc1 = metadata_list[i].start_timecode.to_seconds()
                tc2 = metadata_list[j].start_timecode.to_seconds()
                offset = tc1 - tc2

                # Only include if timecodes are close enough to suggest same recording
                if abs(offset) < metadata_list[i].duration_seconds + metadata_list[j].duration_seconds:
                    pairs.append((i, j, offset))

        return pairs

    def find_gps_sync_pairs(
        self,
        metadata_list: List[MediaMetadata],
        max_distance_meters: float = 100.0
    ) -> List[Tuple[int, int, float]]:
        """
        Find clip pairs that were recorded at same GPS location

        Returns list of (idx1, idx2, distance_meters)
        """
        import math

        def haversine_distance(lat1, lon1, lat2, lon2):
            R = 6371000  # Earth radius in meters
            phi1, phi2 = math.radians(lat1), math.radians(lat2)
            dphi = math.radians(lat2 - lat1)
            dlambda = math.radians(lon2 - lon1)
            a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
            return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        pairs = []
        n = len(metadata_list)

        for i in range(n):
            if metadata_list[i].gps is None:
                continue

            for j in range(i + 1, n):
                if metadata_list[j].gps is None:
                    continue

                dist = haversine_distance(
                    metadata_list[i].gps.latitude,
                    metadata_list[i].gps.longitude,
                    metadata_list[j].gps.latitude,
                    metadata_list[j].gps.longitude
                )

                if dist <= max_distance_meters:
                    pairs.append((i, j, dist))

        return pairs

    def extract_batch(
        self,
        file_paths: List[str],
        progress_callback=None,
        max_workers: int = 4
    ) -> List[MediaMetadata]:
        """Extract metadata from multiple files"""
        from concurrent.futures import ThreadPoolExecutor

        results = []
        total = len(file_paths)

        def process_file(idx_path):
            idx, path = idx_path
            try:
                meta = self.extract(path)
                if progress_callback:
                    progress_callback(idx + 1, total, path)
                return meta
            except Exception as e:
                print(f"Error extracting metadata from {path}: {e}")
                return None

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(process_file, enumerate(file_paths)))

        return [r for r in results if r is not None]

    def clear_cache(self):
        """Clear metadata cache"""
        self._cache.clear()
