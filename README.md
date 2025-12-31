# SkyWatch PTZ Control

SkyWatch is a specialized web-based control application for PTZ (Pan-Tilt-Zoom) security cameras, optimized for tracking aircraft. It combines real-time ADS-B radar data with computer vision tracking to provide a powerful tool for plane spotting and aerial monitoring.

## Features

### 📡 ADS-B Integration
- **Real-Time Radar Map**: Visualizes local air traffic relative to your camera's location.
- **Target Selection**: Click on aircraft icons to view detailed telemetry (Altitude, Speed, Distance).
- **Auto-Slew**: Automatically points the camera at selected ADS-B targets (Implementation dependent on calibration).

### 🎯 Precision Tracking
- **Computer Vision Tracking**: Click on any object in the video feed (or press SPACE to track the center) to lock on using a CSRT/Kalman Filter hybrid tracker.
- **Digital Stabilization (DSTAB)**: A software-stabilized "Locked On" view that keeps the target centered even if the mechanical PTZ movement lags or jitters. Toggle with **`Z`**.
- **Dynamic Speed Control**: Intelligent speed scaling prevents overshooting at high zoom levels.

### 🎥 Control & Recording
- **Web Interface**: Low-latency MJPEG stream accessible from any browser.
- **Video Recording**: Capture the main feed directly to your Downloads folder with a single click or keypress (**`\`** or **`\``**).
- **Hybrid Controls**: Support for both keyboard shortcuts (WASD) and UI buttons.

## Installation

1. **Prerequisites**: Python 3.9+ and pip.
2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Configuration**: 
   - Rename/Edit `config.py` (if applicable) or modify the existing `config.py`.
   - Set your **Camera IP**, **VISCA Port**, and **ADS-B Feed URL**.
   - Update `CAMERA_LAT`, `CAMERA_LNG`, and `CAMERA_HEIGHT_FT` for accurate radar mapping.

## Usage

Run the application:
```bash
python app.py
# or
./launch_skywatch.sh
```
Access the interface at `http://localhost:5001`.

### Controls

| Key | Action |
| :--- | :--- |
| **W / A / S / D** | Pan and Tilt Camera |
| **R / F** | Zoom In / Out |
| **SPACE** | **Toggle Tracking** (Locks on center reticle or clicked target) |
| **Z** | **Toggle Digital Stabilization** (Centers tracking target in view) |
| **`** (Backtick) | **Toggle Recording** |
| **Q / E** | Decrease / Increase Max Speed Limit |
| **1 - 6** | Tune PID Values (P: 1/2, I: 3/4, D: 5/6) |

### On-Screen Display (OSD)
- **Top Left**: System Status, Date/Time (UTC & Local).
- **Bottom**: PID values, Max Speed, and Status Indicators.
- **Gauges**: Visual indicators for Pan Azimuth, Tilt Elevation, and Zoom Level.

## Versioning
Current Version: **v0.8.0 Alpha**
defined in `config.py`.
