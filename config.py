# Camera Configuration
CAMERA_IP = "192.168.1.191"
RTSP_PORT = 554
VISCA_PORT = 1259 # User specified UDP port
CAMERA_WIDTH = 1920
CAMERA_HEIGHT = 1080

# RTSP Stream URL
# User reported just IP:Port works in VLC, implying root path or auto-detect.
# We'll try the root path first.
RTSP_URL = f"rtsp://{CAMERA_IP}:{RTSP_PORT}/"

# Control Loop Settings
LOOP_INTERVAL = 0.033  # ~30 FPS

# PID Controller Settings
# Proportional Gain: Higher = faster response, but more overshoot
# PID Controller Settings
# These values are multipliers for the pixel error.
# Range: Typically 0.01 to 2.0.
# Proportional Gain (KP): Main drive. Higher = faster response to error.
PAN_KP = 0.5
TILT_KP = 0.5

# Derivative Gain: Dampens the movement
PAN_KD = 0.9
TILT_KD = 0.9

# Integral Gain: Accumulates error to eliminate steady-state lag
PAN_KI = 0.05
TILT_KI = 0.05

# Integral Limit (Anti-Windup)
# Max speed contribution from I-term (e.g. 5 means max +/- 5 speed added)
# Irrelevant when KI is 0, but kept low just in case
INTEGRAL_MAX = 1.0

# Speed Smoothing Factor (0.0 to 1.0)
# Lower = smoother but more laggy. Higher = more responsive.
# Set to 1.0 (Instant) to disable smoothing (recommended for low latency).
SPEED_SMOOTHING = 0.5

# Invert Axis (Set to True if camera moves in opposite direction)
PAN_INVERT = True  # Fixed: Object Right -> Error Negative -> Needs Positive Speed (Right) 
TILT_INVERT = False

# Deadband (pixels) - Camera won't move if error is within this range
DEADBAND = 10

# Latency Compensation (Disabled)
# LATENCY_FACTOR = 0.5

# Velocity Smoothing (Disabled)
# VELOCITY_SMOOTHING = 0.6

# Kalman Filter & Feed Forward Settings
# Process Noise: Lower = smoother model, Higher = more responsive to erratic movement
KF_PROCESS_NOISE = 1e-5 
# Measurement Noise: Higher = trust model more (smoother), Lower = trust tracker more (jittery)
KF_MEASUREMENT_NOISE = 1e-1

# Feed Forward Gain
# Multiplier to convert pixels/sec velocity into VISCA speed units.
# Needs tuning! Start small.
# If object moves 100 px/sec, and we want speed 5, Gain = 0.05.
FEED_FORWARD_GAIN = 0.05

# System Latency Compensation (Seconds)
# Time from "Real World Event" to "Frame Processed"
# Includes: Camera Encode + Network + Decode + CV Processing
# If the camera lags behind moving objects, INCREASE this.
# If it overshoots/oscillates, DECREASE this.
SYSTEM_LATENCY = 0.2

# VISCA Speed Limits (1-24 for Pan, 1-20 for Tilt usually)
# Reduced max speeds to help with overshooting
# VISCA Speed Limits (1-24 for Pan, 1-20 for Tilt usually)
# Reduced max speeds to help with overshooting
MAX_PAN_SPEED = 6 # Increased to 6 to allow dynamic range to work
MAX_TILT_SPEED = 6
# Increased min speed to overcome static friction (stiction)
# Reduced to 1 to allow very slow movements without overshooting
MIN_PAN_SPEED = 1
MIN_TILT_SPEED = 1

# Dynamic Speed Control Ranges
# Format: (Distance Threshold in Pixels, Max Speed)
# The logic will use the smallest threshold that the error fits into.
# If error is larger than the largest threshold, it uses the global MAX_PAN_SPEED.
DYNAMIC_SPEED_RANGES = [
    (50, 0.5),   # Very close: Crawl
    (100, 1.0),  # Close: Slow
    (200, 2.0),  # Medium: Moderate
    (300, 4.0),  # Far: Fast
    # > 300 uses MAX_PAN_SPEED (e.g. 5)
]

# Manual Control Settings
MANUAL_SPEED = 8 # Speed for WASD controls
ZOOM_SPEED = 3 # Speed for Zoom controls (1-7)

# Overlay Settings
OVERLAY_IMAGE_PATH = "PTZ overlay.png"

# Target Acquisition Settings
RETICLE_SIZE = 50 # Size of the center box in pixels
# DETECTION_THRESHOLD = 50 # Edge density threshold for "Object Detected" cue

# Digital Stabilization Settings
DIGITAL_STABILIZATION_ENABLED = False # Default state
DIGITAL_CROP_FACTOR = 0.5 # 1.0 = No Crop, 0.8 = 20% Zoom/Crop


# VISCA Calibration / Mapping
# These values need to be calibrated for the specific camera.
# Defaults are based on common PTZOptics/Sony VISCA specs.

# Pan: Hex Range -> Degree Range
# Sony: Center=0, Right=Positive, Left=Negative (or vice versa depending on mount)
# Range: often -0x1234 to +0x1234 for -170 to +170 degrees
# Let's assume a linear scale. 
# For many cameras: 0x0000 is center. 
# Max Pan (e.g. 170 deg) = 0x0990 (2448) roughly? Or 0xF...
# We will use a "Counts per Degree" factor.
# Common approximation: 24 counts per degree?
# Let's try: 0 deg = 0x0000.
PAN_COUNTS_PER_DEGREE = 24.0 
TILT_COUNTS_PER_DEGREE = 24.0

# Zoom: Hex Range -> Zoom Factor
# Wide = 0x0000 = 1x
# Tele = 0x4000 (16384) = Max Zoom (e.g. 20x or 30x)
ZOOM_MAX_HEX = 0x4000
ZOOM_MAX_X = 20.0 # Change this to your camera's max zoom (e.g. 12, 20, 30)

# Camera Mechanical Limits (Degrees)
PAN_MIN_DEG = -170
PAN_MAX_DEG = 170
TILT_MIN_DEG = -30 # Down
TILT_MAX_DEG = 90  # Up

# Location & Radar Settings
CAMERA_LAT = 37.818728
CAMERA_LNG = -122.268427
CAMERA_HEIGHT_FT = 60
FOV_RIGHT = 285 # degrees true heading (approx limit)
FOV_LEFT = 198  # degrees true heading (approx limit)
MAX_RANGE_NM = 10

# ADS-B Feed
ADSB_URL = "http://adsb-feeder.local:8080/data/aircraft.json"
