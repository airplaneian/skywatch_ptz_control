import os
import yaml

# --- Load Configuration ---
def load_config():
    config_path = "config.yaml"
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Error loading config.yaml: {e}")
            return {}
    return {}

_cfg = load_config()

def get_cfg(path, default):
    """Safe deep get for config dictionary"""
    keys = path.split('.')
    val = _cfg
    for key in keys:
        if isinstance(val, dict) and key in val:
            val = val[key]
        else:
            return default
    return val

# --- Camera Configuration ---
CAMERA_IP = get_cfg('camera.ip', "192.168.1.191")
RTSP_PORT = get_cfg('camera.rtsp_port', 554)
VISCA_PORT = get_cfg('camera.visca_port', 1259)
CAMERA_WIDTH = 1920
CAMERA_HEIGHT = 1080
APP_VERSION = "0.9.0 Beta"

# RTSP Stream URL
# Allow full override from config, else construct
_rtsp_manual = get_cfg('camera.rtsp_url', None)
if _rtsp_manual:
    RTSP_URL = _rtsp_manual
else:
    RTSP_URL = f"rtsp://{CAMERA_IP}:{RTSP_PORT}/"

# --- Control Loop Settings ---
LOOP_INTERVAL = 0.033  # ~30 FPS

# --- PID Controller Settings ---
PAN_KP = get_cfg('control.pan_kp', 0.5)
TILT_KP = get_cfg('control.tilt_kp', 0.5)
PAN_KD = get_cfg('control.pan_kd', 0.9)
TILT_KD = get_cfg('control.tilt_kd', 0.9)
PAN_KI = get_cfg('control.pan_ki', 0.05)
TILT_KI = get_cfg('control.tilt_ki', 0.05)

# Integral Limit (Anti-Windup)
INTEGRAL_MAX = 1.0

# Speed Smoothing
SPEED_SMOOTHING = 0.5

# Invert Axis
PAN_INVERT = get_cfg('camera.mechanics.invert_pan', True)
TILT_INVERT = get_cfg('camera.mechanics.invert_tilt', False)

# Deadband
DEADBAND = 10

# --- Kalman Filter & Feed Forward ---
KF_PROCESS_NOISE = 1e-5 
KF_MEASUREMENT_NOISE = 1e-1
FEED_FORWARD_GAIN = 0.05
SYSTEM_LATENCY = 0.2

# --- VISCA Speed Limits ---
MAX_PAN_SPEED = get_cfg('camera.mechanics.max_pan_speed', 6)
MAX_TILT_SPEED = get_cfg('camera.mechanics.max_tilt_speed', 6)
MIN_PAN_SPEED = get_cfg('camera.mechanics.min_pan_speed', 1)
MIN_TILT_SPEED = get_cfg('camera.mechanics.min_tilt_speed', 1)

# Dynamic Speed Control Ranges
DYNAMIC_SPEED_RANGES = [
    (50, 0.5),   # Very close
    (100, 1.0),  # Close
    (200, 2.0),  # Medium
    (300, 4.0),  # Far
]

# --- Manual Control Settings ---
MANUAL_SPEED = 8
ZOOM_SPEED = 3

# --- Overlay Settings ---
OVERLAY_IMAGE_PATH = "PTZ overlay.png"

# --- Target Acquisition Settings ---
RETICLE_SIZE = 50 

# --- Digital Stabilization Settings ---
DIGITAL_STABILIZATION_ENABLED = False
DIGITAL_CROP_FACTOR = 0.5

# --- VISCA Calibration / Mapping ---
PAN_COUNTS_PER_DEGREE = get_cfg('camera.mechanics.pan_counts_per_degree', 24.0)
TILT_COUNTS_PER_DEGREE = get_cfg('camera.mechanics.tilt_counts_per_degree', 24.0)
ZOOM_MAX_HEX = get_cfg('camera.mechanics.zoom_max_hex', 0x4000)
ZOOM_MAX_X = get_cfg('camera.mechanics.zoom_max_x', 20.0)

# Camera Mechanical Limits
PAN_MIN_DEG = -170
PAN_MAX_DEG = 170
TILT_MIN_DEG = -30
TILT_MAX_DEG = 90

# --- Location & Radar Settings ---
CAMERA_LAT = get_cfg('location.lat', 37.818728)
CAMERA_LNG = get_cfg('location.lng', -122.268427)
CAMERA_HEIGHT_FT = get_cfg('location.alt_ft', 60)
FOV_RIGHT = 285
FOV_LEFT = 198
MAX_RANGE_NM = get_cfg('adsb.max_range_nm', 10)

# --- ADS-B Feed ---
ADSB_URL = get_cfg('adsb.url', "http://adsb-feeder.local:8080/data/aircraft.json")
