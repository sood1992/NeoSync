"""
NeoSync Setup
=============

Installation script for NeoSync.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read version
version = "1.0.0"

# Read README
readme_path = Path(__file__).parent / "README.md"
long_description = ""
if readme_path.exists():
    long_description = readme_path.read_text(encoding="utf-8")

setup(
    name="neosync",
    version=version,
    author="NeoFox",
    author_email="info@neofox.com",
    description="Professional Audio/Video Synchronization Tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/neofox/neosync",
    packages=find_packages(),
    include_package_data=True,
    python_requires=">=3.10",
    install_requires=[
        "PyQt6>=6.5.0",
        "numpy>=1.24.0",
        "scipy>=1.10.0",
        "librosa>=0.10.0",
        "soundfile>=0.12.0",
        "opencv-python>=4.8.0",
        "Pillow>=10.0.0",
        "noisereduce>=2.0.0",
        "exifread>=3.0.0",
    ],
    extras_require={
        "gpu": [
            "cupy-cuda12x>=12.0.0",
        ],
        "reports": [
            "reportlab>=4.0.0",
        ],
        "aaf": [
            "pyaaf2>=1.6.0",
        ],
        "dev": [
            "pytest>=7.0.0",
            "pytest-qt>=4.0.0",
            "black>=23.0.0",
            "mypy>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "neosync=neosync.__main__:main",
        ],
        "gui_scripts": [
            "neosync-gui=neosync.__main__:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: MacOS X",
        "Environment :: Win32 (MS Windows)",
        "Environment :: X11 Applications :: Qt",
        "Intended Audience :: End Users/Desktop",
        "License :: Other/Proprietary License",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows :: Windows 10",
        "Operating System :: Microsoft :: Windows :: Windows 11",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Multimedia :: Sound/Audio",
        "Topic :: Multimedia :: Video",
    ],
    keywords="audio video sync synchronization multicam pluraleyes",
)
