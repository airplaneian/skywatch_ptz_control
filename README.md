# SkyWatch PTZ Control

## Project Philosophy
**SkyWatch** was created to explore the limits of an inexpensive, off-the-shelf PTZ (Pan-Tilt-Zoom) camera. While these cameras are typically designed for stationary subjects in conference rooms, this project aims to adapt one for tracking fast-moving targets (specifically aircraft) by implementing custom control software.

The goal is to improve tracking performance and provide better situational awareness than the standard camera software allows, applying principles like sensor fusion and control theory to consumer hardware.

## System Architecture

### 1. Hybrid Tracking Engine
Tracking non-cooperative targets like aircraft against complex backgrounds is handled by combining two approaches:
-   **Visual Tracking (CSRT)**: Uses the OpenCV CSRT tracker to maintain a visual lock on the object's texture.
-   **State Estimation (Kalman Filter)**: A Kalman Filter is used to estimate the position and velocity of the aircraft. This helps smooth out noisy detection data and allows the system to predict the object's location during brief occlusions or tracking failures.

### 2. Mechanical Control Loop
To address the latency and mechanical inertia inherent in these cameras, the visible error is processed through a custom control loop:
-   **PID Controller**: Calculates the pan/tilt velocity needed to center the target based on current position error.
-   **Feed Forward**: Uses the velocity estimate from the Kalman Filter to proactively move the camera, improving response time.
-   **Dynamic Speed Scaling**: Automatically adjusts control sensitivity based on the zoom level, reducing the likelihood of overshooting at high magnification.

### 3. Digital Stabilization
Mechanical motors have step limits that can cause jitter at high zoom levels. To address this, **Digital Stabilization** can be enabled.
-   **Virtual Gimbal**: The software crops the video feed (e.g., from 1080p to a smaller window) and adjusts this window's position frame-by-frame to keep the tracked target centered, smoothing out residual mechanical movement.

### 4. Situational Awareness (ADS-B Integration)
The system integrates with a local **ADS-B Receiver** (e.g., `dump1090`) to provide context.
-   **Mini Map**: Visualizes local air traffic relative to the camera's azimuth.
-   **Automatic Telemetry**: When an aircraft is centered in the view, the system correlates the camera's pointing angle with known aircraft positions to display available telemetry (Altitude, Speed, Tail Number). Note: This relies on the camera's position reporting and does not control the camera itself.

---

## Installation

### Prerequisites
-   Python 3.9+
-   A VISCA-over-IP compatible PTZ Camera (Sony, PTZOptics, or generic clones)
-   Local ADS-B Feeder (Optional, for telemetry)

### Setup
1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
2.  **Configuration**: 
    Edit `config.py` to match your hardware environment.
    -   `CAMERA_IP`: The static IP of your PTZ camera.
    -   `CAMERA_LAT`/`LON`/`HEIGHT`: Your physical location (critical for accurate ADS-B mapping).
    -   `ADSB_URL`: The JSON endpoint of your local feeder (usually `http://<pi-ip>:8080/data/aircraft.json`).

## Operation Guide

Run the application:
```bash
./launch_skywatch.sh
```
Access the interface at `http://localhost:5001`.

### Controls

| Key | Function | Description |
| :--- | :--- | :--- |
| **WASD** | **Manual Slew** | Manually steer the camera. |
| **R / F** | **Zoom** | Zoom In / Zoom Out. |
| **SPACE** | **Engage Track** | Locks onto the object in the crosshairs. Press again to disengage. |
| **Z** | **Stabilizer** | Toggles Digital Stabilization. |
| **`** | **Record** | Saves the current feed to disk. |
| **Q / E** | **Speed Limiter** | Adjusts the maximum slew rate. |

### Tuning
If the camera oscillates or lags:
-   **P (Proportional)**: Increase if valid targets are escaping the frame. Decrease if the camera overshoots.
-   **I (Integral)**: Increase to reduce steady-state error (lag behind the target).
-   **D (Derivative)**: Increase to dampen movement and reduce oscillation.
