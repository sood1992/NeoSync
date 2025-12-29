"""
Telemetry Extractor
===================

Extract telemetry data from:
- DJI drones (SRT subtitle files)
- GoPro cameras (GPMF format)
- Generic GPS/IMU data

This enables sync for silent footage using GPS timestamps and motion correlation.
"""

import re
import os
import struct
import json
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import subprocess

import numpy as np


@dataclass
class GPSPoint:
    """Single GPS measurement"""
    timestamp: datetime
    latitude: float
    longitude: float
    altitude: float = 0.0
    speed_2d: float = 0.0
    speed_3d: float = 0.0
    dop: float = 0.0  # Dilution of precision
    fix_type: int = 0  # 0=none, 2=2D, 3=3D


@dataclass
class IMUPoint:
    """Single IMU measurement"""
    timestamp: float  # Seconds from start
    accel_x: float
    accel_y: float
    accel_z: float
    gyro_x: float = 0.0
    gyro_y: float = 0.0
    gyro_z: float = 0.0


@dataclass
class CameraSettings:
    """Camera settings at a point in time"""
    timestamp: datetime
    iso: int = 0
    shutter: float = 0.0  # As fraction (1/320 = 0.003125)
    fnum: float = 0.0  # f-stop
    ev: float = 0.0  # Exposure value


@dataclass
class TelemetryData:
    """Complete telemetry data for a clip"""
    file_path: str
    source: str  # 'dji_srt', 'gopro_gpmf', 'exif', etc.

    # Time info
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration: float = 0.0

    # GPS track
    gps_points: List[GPSPoint] = field(default_factory=list)
    gps_rate_hz: float = 0.0

    # IMU data
    imu_points: List[IMUPoint] = field(default_factory=list)
    accel_rate_hz: float = 0.0
    gyro_rate_hz: float = 0.0

    # Camera settings
    camera_settings: List[CameraSettings] = field(default_factory=list)

    # Device info
    device_name: Optional[str] = None
    device_model: Optional[str] = None
    firmware: Optional[str] = None

    @property
    def has_gps(self) -> bool:
        return len(self.gps_points) > 0

    @property
    def has_imu(self) -> bool:
        return len(self.imu_points) > 0

    def get_gps_timestamps_unix(self) -> np.ndarray:
        """Get GPS timestamps as Unix epoch seconds"""
        if not self.gps_points:
            return np.array([])
        return np.array([p.timestamp.timestamp() for p in self.gps_points])

    def get_accel_array(self) -> np.ndarray:
        """Get accelerometer data as Nx3 array"""
        if not self.imu_points:
            return np.array([])
        return np.array([[p.accel_x, p.accel_y, p.accel_z] for p in self.imu_points])

    def get_gyro_array(self) -> np.ndarray:
        """Get gyroscope data as Nx3 array"""
        if not self.imu_points:
            return np.array([])
        return np.array([[p.gyro_x, p.gyro_y, p.gyro_z] for p in self.imu_points])


class DJISRTParser:
    """
    Parse DJI drone SRT subtitle files

    DJI embeds telemetry in SRT format with varying rates:
    - Phantom 3/4: ~1 Hz
    - Mavic Air 2/2S: ~30 Hz
    - Mavic 3/Mini 4 Pro: Protobuf format (more complex)

    Format example:
    1
    00:00:00,033 --> 00:00:00,066
    FrameCnt: 2, DiffTime: 33ms
    2024-03-20 12:59:17.852
    [iso: 400] [shutter: 1/320.0] [fnum: 1.7]
    [latitude: 30.123456] [longitude: -81.654321]
    [rel_alt: 6.500 abs_alt: -32.309]
    """

    # Regex patterns for DJI SRT
    DATETIME_PATTERN = re.compile(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)')
    LATITUDE_PATTERN = re.compile(r'\[latitude:\s*([-\d.]+)\]')
    LONGITUDE_PATTERN = re.compile(r'\[longitude:\s*([-\d.]+)\]')
    ALTITUDE_PATTERN = re.compile(r'\[(?:rel_alt|altitude):\s*([-\d.]+)')
    ABS_ALT_PATTERN = re.compile(r'\[abs_alt:\s*([-\d.]+)\]')
    ISO_PATTERN = re.compile(r'\[iso:\s*(\d+)\]')
    SHUTTER_PATTERN = re.compile(r'\[shutter:\s*1/([\d.]+)\]')
    FNUM_PATTERN = re.compile(r'\[fnum:\s*([\d.]+)\]')
    FRAMECNT_PATTERN = re.compile(r'FrameCnt:\s*(\d+)')
    DIFFTIME_PATTERN = re.compile(r'DiffTime:\s*(\d+)ms')

    def parse(self, srt_path: str) -> TelemetryData:
        """Parse DJI SRT file"""
        telemetry = TelemetryData(
            file_path=srt_path,
            source='dji_srt',
            device_name='DJI Drone'
        )

        if not os.path.exists(srt_path):
            return telemetry

        with open(srt_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Split into subtitle entries
        entries = re.split(r'\n\n+', content.strip())

        for entry in entries:
            if not entry.strip():
                continue

            # Extract datetime
            dt_match = self.DATETIME_PATTERN.search(entry)
            if not dt_match:
                continue

            try:
                dt_str = dt_match.group(1)
                # Handle various datetime formats
                if '.' in dt_str:
                    timestamp = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S.%f')
                else:
                    timestamp = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                continue

            # Extract GPS
            lat_match = self.LATITUDE_PATTERN.search(entry)
            lon_match = self.LONGITUDE_PATTERN.search(entry)
            alt_match = self.ALTITUDE_PATTERN.search(entry)

            if lat_match and lon_match:
                gps_point = GPSPoint(
                    timestamp=timestamp,
                    latitude=float(lat_match.group(1)),
                    longitude=float(lon_match.group(1)),
                    altitude=float(alt_match.group(1)) if alt_match else 0.0,
                    fix_type=3  # Assume 3D fix
                )
                telemetry.gps_points.append(gps_point)

            # Extract camera settings
            iso_match = self.ISO_PATTERN.search(entry)
            shutter_match = self.SHUTTER_PATTERN.search(entry)
            fnum_match = self.FNUM_PATTERN.search(entry)

            if iso_match or shutter_match or fnum_match:
                settings = CameraSettings(
                    timestamp=timestamp,
                    iso=int(iso_match.group(1)) if iso_match else 0,
                    shutter=1.0 / float(shutter_match.group(1)) if shutter_match else 0,
                    fnum=float(fnum_match.group(1)) if fnum_match else 0
                )
                telemetry.camera_settings.append(settings)

        # Calculate metadata
        if telemetry.gps_points:
            telemetry.start_time = telemetry.gps_points[0].timestamp
            telemetry.end_time = telemetry.gps_points[-1].timestamp
            telemetry.duration = (telemetry.end_time - telemetry.start_time).total_seconds()

            if telemetry.duration > 0:
                telemetry.gps_rate_hz = len(telemetry.gps_points) / telemetry.duration

        return telemetry

    def find_srt_for_video(self, video_path: str) -> Optional[str]:
        """Find matching SRT file for a video"""
        base = os.path.splitext(video_path)[0]

        # Try common patterns
        candidates = [
            f"{base}.srt",
            f"{base}.SRT",
            f"{base}_subtitle.srt",
        ]

        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate

        return None


class GoProGPMFParser:
    """
    Parse GoPro GPMF (GoPro Metadata Format) from MP4 files

    GPMF is a binary KLV format storing:
    - GPS5: lat, lon, alt, 2D speed, 3D speed @ ~18Hz (HERO5-10)
    - GPS9: GPS5 + time, DOP, fix @ ~10Hz (HERO11+)
    - ACCL: 3-axis accelerometer @ 200Hz
    - GYRO: 3-axis gyroscope @ 400Hz
    - CORI: Camera orientation quaternions
    - IORI: Image orientation

    Note: HERO12 removed GPS receiver entirely!
    """

    # GPMF FourCC codes
    FOURCC_DEVC = b'DEVC'  # Device container
    FOURCC_STRM = b'STRM'  # Stream container
    FOURCC_DVNM = b'DVNM'  # Device name
    FOURCC_GPS5 = b'GPS5'  # GPS data (5 fields)
    FOURCC_GPS9 = b'GPS9'  # GPS data (9 fields)
    FOURCC_GPSU = b'GPSU'  # GPS UTC time string
    FOURCC_ACCL = b'ACCL'  # Accelerometer
    FOURCC_GYRO = b'GYRO'  # Gyroscope
    FOURCC_SCAL = b'SCAL'  # Scale factors
    FOURCC_TMPC = b'TMPC'  # Temperature
    FOURCC_ORIO = b'ORIO'  # Orientation matrix

    def __init__(self):
        self.ffprobe_path = self._find_ffprobe()

    def _find_ffprobe(self) -> Optional[str]:
        import shutil
        return shutil.which('ffprobe')

    def parse(self, video_path: str) -> TelemetryData:
        """Parse GoPro GPMF telemetry from video file"""
        telemetry = TelemetryData(
            file_path=video_path,
            source='gopro_gpmf'
        )

        # Try Python library first
        try:
            return self._parse_with_library(video_path, telemetry)
        except ImportError:
            pass

        # Fall back to FFprobe extraction
        try:
            return self._parse_with_ffprobe(video_path, telemetry)
        except Exception as e:
            print(f"GPMF parse error: {e}")
            return telemetry

    def _parse_with_library(self, video_path: str, telemetry: TelemetryData) -> TelemetryData:
        """Parse using gopro_telemetry or gpmf-parser library"""
        try:
            from gpmf import GPMFParser
            parser = GPMFParser(video_path)

            # Extract GPS
            gps_data = parser.get_gps()
            if gps_data:
                for point in gps_data:
                    telemetry.gps_points.append(GPSPoint(
                        timestamp=point['timestamp'],
                        latitude=point['latitude'],
                        longitude=point['longitude'],
                        altitude=point.get('altitude', 0),
                        speed_2d=point.get('speed_2d', 0),
                        speed_3d=point.get('speed_3d', 0)
                    ))

            # Extract accelerometer
            accel_data = parser.get_accelerometer()
            if accel_data:
                for i, point in enumerate(accel_data):
                    telemetry.imu_points.append(IMUPoint(
                        timestamp=i / 200.0,  # Approximate timing
                        accel_x=point[0],
                        accel_y=point[1],
                        accel_z=point[2]
                    ))

            # Extract gyroscope
            gyro_data = parser.get_gyroscope()
            if gyro_data and telemetry.imu_points:
                for i, point in enumerate(gyro_data):
                    if i < len(telemetry.imu_points):
                        telemetry.imu_points[i].gyro_x = point[0]
                        telemetry.imu_points[i].gyro_y = point[1]
                        telemetry.imu_points[i].gyro_z = point[2]

            # Device info
            telemetry.device_name = 'GoPro'
            telemetry.device_model = parser.get_device_name()

            return telemetry

        except Exception:
            raise ImportError("GPMF library not available")

    def _parse_with_ffprobe(self, video_path: str, telemetry: TelemetryData) -> TelemetryData:
        """Extract metadata using FFprobe (limited data)"""
        if not self.ffprobe_path:
            return telemetry

        try:
            cmd = [
                self.ffprobe_path,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            data = json.loads(result.stdout)

            # Look for GoPro MET stream
            for stream in data.get('streams', []):
                if stream.get('codec_tag_string') == 'gpmd':
                    telemetry.device_name = 'GoPro'
                    break

            # Extract creation time
            fmt = data.get('format', {})
            tags = fmt.get('tags', {})
            creation_time = tags.get('creation_time')
            if creation_time:
                try:
                    telemetry.start_time = datetime.fromisoformat(
                        creation_time.replace('Z', '+00:00')
                    )
                except:
                    pass

        except Exception as e:
            print(f"FFprobe error: {e}")

        return telemetry

    def has_gpmf_track(self, video_path: str) -> bool:
        """Check if video has GPMF metadata track"""
        if not self.ffprobe_path:
            return False

        try:
            cmd = [
                self.ffprobe_path,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_streams',
                video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            data = json.loads(result.stdout)

            for stream in data.get('streams', []):
                if stream.get('codec_tag_string') == 'gpmd':
                    return True
                if 'GoPro' in stream.get('tags', {}).get('handler_name', ''):
                    return True

            return False

        except:
            return False


class TelemetryExtractor:
    """
    Unified telemetry extraction from any media source

    Supports:
    - DJI drones (SRT files)
    - GoPro cameras (GPMF)
    - Generic GPS from EXIF
    - Insta360 (TODO)
    """

    def __init__(self):
        self.dji_parser = DJISRTParser()
        self.gopro_parser = GoProGPMFParser()
        self._cache: Dict[str, TelemetryData] = {}

    def extract(self, file_path: str) -> TelemetryData:
        """Extract telemetry from any supported file"""
        file_path = str(Path(file_path).resolve())

        # Check cache
        if file_path in self._cache:
            return self._cache[file_path]

        # Try different sources
        telemetry = TelemetryData(file_path=file_path, source='none')

        # 1. Check for DJI SRT file
        srt_path = self.dji_parser.find_srt_for_video(file_path)
        if srt_path:
            telemetry = self.dji_parser.parse(srt_path)
            if telemetry.has_gps:
                self._cache[file_path] = telemetry
                return telemetry

        # 2. Check for GoPro GPMF
        if self.gopro_parser.has_gpmf_track(file_path):
            telemetry = self.gopro_parser.parse(file_path)
            if telemetry.has_gps or telemetry.has_imu:
                self._cache[file_path] = telemetry
                return telemetry

        # 3. Try EXIF GPS (images/videos with GPS tags)
        telemetry = self._extract_exif_gps(file_path)

        self._cache[file_path] = telemetry
        return telemetry

    def _extract_exif_gps(self, file_path: str) -> TelemetryData:
        """Extract GPS from EXIF metadata"""
        telemetry = TelemetryData(file_path=file_path, source='exif')

        try:
            import exifread
            with open(file_path, 'rb') as f:
                tags = exifread.process_file(f, details=False)

            lat = self._convert_exif_gps(tags.get('GPS GPSLatitude'), tags.get('GPS GPSLatitudeRef'))
            lon = self._convert_exif_gps(tags.get('GPS GPSLongitude'), tags.get('GPS GPSLongitudeRef'))

            if lat is not None and lon is not None:
                # Try to get timestamp
                dt_str = str(tags.get('EXIF DateTimeOriginal', ''))
                if dt_str:
                    try:
                        timestamp = datetime.strptime(dt_str, '%Y:%m:%d %H:%M:%S')
                    except:
                        timestamp = datetime.now()
                else:
                    timestamp = datetime.now()

                telemetry.gps_points.append(GPSPoint(
                    timestamp=timestamp,
                    latitude=lat,
                    longitude=lon
                ))
                telemetry.start_time = timestamp

        except ImportError:
            pass
        except Exception as e:
            print(f"EXIF extraction error: {e}")

        return telemetry

    def _convert_exif_gps(self, coord_tag, ref_tag) -> Optional[float]:
        """Convert EXIF GPS coordinate to decimal degrees"""
        if coord_tag is None:
            return None

        try:
            values = coord_tag.values
            # Safely handle division, avoid div by zero
            den0 = float(values[0].den) if values[0].den != 0 else 1.0
            den1 = float(values[1].den) if values[1].den != 0 else 1.0
            den2 = float(values[2].den) if values[2].den != 0 else 1.0

            degrees = float(values[0].num) / den0
            minutes = float(values[1].num) / den1
            seconds = float(values[2].num) / den2

            decimal = degrees + minutes / 60 + seconds / 3600

            if ref_tag and str(ref_tag) in ['S', 'W']:
                decimal = -decimal

            return decimal
        except:
            return None

    def sync_by_gps_time(
        self,
        telemetry1: TelemetryData,
        telemetry2: TelemetryData
    ) -> Optional[float]:
        """
        Calculate time offset between two clips using GPS timestamps

        GPS time provides atomic-clock-derived precision when available.
        Returns offset in seconds (positive = clip2 is ahead)
        """
        if not telemetry1.has_gps or not telemetry2.has_gps:
            return None

        if telemetry1.start_time is None or telemetry2.start_time is None:
            return None

        # Calculate offset from GPS timestamps
        offset = (telemetry2.start_time - telemetry1.start_time).total_seconds()

        return offset

    def sync_by_imu_correlation(
        self,
        telemetry1: TelemetryData,
        telemetry2: TelemetryData,
        max_offset_seconds: float = 60.0
    ) -> Optional[Tuple[float, float]]:
        """
        Sync using IMU (accelerometer/gyroscope) correlation

        Useful when cameras experienced similar motion (same vehicle, rig, etc.)
        Returns (offset_seconds, correlation_confidence)
        """
        if not telemetry1.has_imu or not telemetry2.has_imu:
            return None

        try:
            from scipy import signal
            from scipy.interpolate import interp1d

            # Get acceleration magnitude (motion intensity)
            accel1 = telemetry1.get_accel_array()
            accel2 = telemetry2.get_accel_array()

            if len(accel1) < 100 or len(accel2) < 100:
                return None

            # Compute magnitude
            mag1 = np.sqrt(np.sum(accel1 ** 2, axis=1))
            mag2 = np.sqrt(np.sum(accel2 ** 2, axis=1))

            # Normalize
            mag1 = (mag1 - np.mean(mag1)) / (np.std(mag1) + 1e-10)
            mag2 = (mag2 - np.mean(mag2)) / (np.std(mag2) + 1e-10)

            # Cross-correlation
            correlation = signal.correlate(mag1, mag2, mode='full')
            lags = signal.correlation_lags(len(mag1), len(mag2), mode='full')

            # Convert lags to seconds (assuming 200Hz IMU rate)
            sample_rate = telemetry1.accel_rate_hz or 200.0
            max_lag = int(max_offset_seconds * sample_rate)

            # Limit search range
            valid_mask = np.abs(lags) <= max_lag
            valid_corr = correlation.copy()
            valid_corr[~valid_mask] = -np.inf

            # Find peak
            peak_idx = np.argmax(valid_corr)
            peak_lag = lags[peak_idx]
            peak_value = correlation[peak_idx]

            # Convert to seconds
            offset_seconds = peak_lag / sample_rate

            # Calculate confidence (normalized correlation)
            confidence = peak_value / (len(mag1) * np.std(mag1) * np.std(mag2) + 1e-10)
            confidence = min(1.0, max(0.0, confidence))

            return offset_seconds, confidence

        except ImportError:
            return None
        except Exception as e:
            print(f"IMU correlation error: {e}")
            return None

    def clear_cache(self):
        """Clear telemetry cache"""
        self._cache.clear()
