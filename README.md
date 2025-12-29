# NeoSync

**Professional Audio/Video Synchronization Tool**

NeoSync is a powerful, GPU-accelerated sync tool for professional video production. It synchronizes 5-500+ clips with sub-sample accuracy, using multiple sync methods including audio waveform matching, visual detection, GPS timestamps, and timecode.

![NeoSync Screenshot](assets/screenshot.png)

## Features

### Multi-Method Synchronization
- **Audio Waveform** - GCC-PHAT with sub-sample accuracy
- **Visual Flash Detection** - For clapper/flash sync markers
- **Motion Correlation** - For cameras on same rig/vehicle
- **GPS Timestamps** - From DJI drones and GoPro cameras
- **Timecode** - SMPTE LTC and embedded timecode
- **Metadata** - File creation time matching

### Accuracy Improvements
- Multi-stage matching (coarse fingerprint → fine GCC-PHAT)
- Parabolic interpolation for sub-sample accuracy
- Noise-robust preprocessing with spectral gating
- Multi-point drift detection and time-stretch correction
- Confidence fusion combining all sync methods

### Performance
- GPU acceleration (CUDA/OpenCL)
- Parallel processing (4-8 workers)
- Fingerprint caching for instant re-sync
- Optimized power-of-2 FFT sizes

### Export Formats
- Final Cut Pro XML (FCPXML)
- Adobe Premiere Pro XML
- Avid AAF
- OpenTimelineIO (OTIO)
- CSV/HTML/PDF Reports

### Modern GUI
- Beautiful dark/light themes
- Drag-and-drop interface
- Waveform visualization
- Manual sync adjustment
- Timeline preview
- Keyboard-driven workflow

## Installation

### Windows
1. Download `NeoSync-1.0.0-Setup.exe`
2. Run installer
3. Launch from Start Menu

### macOS
1. Download `NeoSync-1.0.0.dmg`
2. Drag NeoSync to Applications
3. Launch from Launchpad

### From Source
```bash
# Clone repository
git clone https://github.com/neofox/neosync.git
cd neosync

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run
python -m neosync
```

## Quick Start

1. **Add Clips** - Drag and drop or click "Add Clips"
2. **Analyze** - Click "Analyze" to process audio/video
3. **Sync** - Click "Sync All" to synchronize
4. **Export** - Click "Export" to save for your NLE

## Sync Methods Hierarchy

NeoSync uses a fallback hierarchy for maximum accuracy:

1. **GPS PPS** - Sub-microsecond accuracy (DJI/GoPro with GPS)
2. **LTC Timecode** - Frame-accurate (pro cameras with TC)
3. **Audio GCC-PHAT** - 2-20μs accuracy at 48kHz
4. **Visual Flash** - 0.3-0.5ms with rolling shutter analysis
5. **IMU Correlation** - 1-5ms (cameras with motion sensors)
6. **Metadata Time** - ±1-30 seconds (fallback)

## Supported Formats

### Video
- MP4, MOV, MKV, AVI, MXF, M4V, WMV
- RED R3D, BRAW, ARRI ARi

### Audio
- WAV, MP3, AAC, M4A, FLAC

### Telemetry
- DJI SRT (all drone models)
- GoPro GPMF (HERO5-11, excludes HERO12)

## Requirements

- **OS**: Windows 10/11, macOS 10.15+
- **RAM**: 8GB minimum, 16GB recommended
- **GPU**: NVIDIA (CUDA) or AMD (OpenCL) for acceleration
- **Disk**: 500MB + space for media analysis cache

## License

NeoSync requires a license key for full functionality.

- **Trial**: 5 clips, all features
- **Pro**: 500 clips, all features
- **Team**: 1000 clips, priority support
- **Enterprise**: Unlimited clips, custom integration

Contact sales@neofox.com for licensing.

## Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Import clips | Ctrl/Cmd + I |
| Analyze all | Ctrl/Cmd + A |
| Sync all | Ctrl/Cmd + Shift + A |
| Export | Ctrl/Cmd + E |
| Set reference | R |
| Nudge left | ← |
| Nudge right | → |
| Zoom in | + |
| Zoom out | - |
| Remove selected | Delete |

## Credits

Built with ❤️ by NeoFox

© 2024 NeoFox. All rights reserved.
