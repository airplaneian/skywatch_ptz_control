import cv2
import numpy as np
import time
import threading
import math
import os
from datetime import datetime, timezone
import traceback
import config
from video_capture import ThreadedVideoCapture
from visca_control import CameraControl
from kalman_filter import SkyWatchKalman

# --- OSD Drawing Helpers (Moved from main.py) ---
def draw_text(img, text, pos, font, scale, color, thickness=1):
    cv2.putText(img, text, pos, font, scale, (0, 0, 0), thickness + 2, cv2.LINE_AA)
    cv2.putText(img, text, pos, font, scale, color, thickness, cv2.LINE_AA)

def draw_line(img, pt1, pt2, color, thickness=1):
    cv2.line(img, pt1, pt2, (0, 0, 0), thickness + 2, cv2.LINE_AA)
    cv2.line(img, pt1, pt2, color, thickness, cv2.LINE_AA)

def draw_rect(img, pt1, pt2, color, thickness=1):
    cv2.rectangle(img, pt1, pt2, (0, 0, 0), thickness + 2, cv2.LINE_AA)
    cv2.rectangle(img, pt1, pt2, color, thickness, cv2.LINE_AA)

def draw_circle(img, center, radius, color, thickness=1):
    if thickness == -1:
        cv2.circle(img, center, radius, color, -1, cv2.LINE_AA)
        cv2.circle(img, center, radius, (0, 0, 0), 1, cv2.LINE_AA)
    else:
        cv2.circle(img, center, radius, (0, 0, 0), thickness + 2, cv2.LINE_AA)
        cv2.circle(img, center, radius, color, thickness, cv2.LINE_AA)

class SkyWatchCore:
    def __init__(self):
        self.running = False
        self.thread = None
        self.lock = threading.Lock()

        # Camera & Control
        self.ptz = CameraControl(config.CAMERA_IP, config.VISCA_PORT)
        self.video = None
        
        # Overlay
        self.overlay = None
        try:
            self.overlay = cv2.imread(config.OVERLAY_IMAGE_PATH, cv2.IMREAD_UNCHANGED)
        except Exception as e:
            print(f"Warning: Could not load overlay: {e}")

        # State Variables
        self.tracking_active = False
        self.tracker = None
        self.kf = None
        self.digital_stabilization_active = config.DIGITAL_STABILIZATION_ENABLED
        self.current_max_speed = config.MAX_PAN_SPEED
        self.manual_mode_active = False
        
        # PID State
        self.current_kp = config.PAN_KP
        self.current_ki = config.PAN_KI
        self.current_kd = config.PAN_KD
        self.pid_state = {
            'prev_error_x': 0, 'prev_error_y': 0,
            'error_sum_x': 0.0, 'error_sum_y': 0.0,
            'prev_pan_speed': 0.0, 'prev_tilt_speed': 0.0,
            'pan_accumulator': 0.0, 'tilt_accumulator': 0.0,
            'last_sent_pan': 0, 'last_sent_tilt': 0,
            'last_visca_time': 0
        }

        # Recording State
        self.recording = False
        self.video_writer = None
        self.download_dir = os.path.expanduser("~/Downloads")

        # Shared Data for Web (Thread-Safe Inteface)
        self.latest_frame = None # The final frame with OSD
        self.telemetry = {
            'pan': 0, 'tilt': 0, 'zoom': 1.0, # Changed zoom to 1.0
            'kp': self.current_kp, 'ki': self.current_ki, 'kd': self.current_kd, # Used current_kp etc.
            'speed_limit': self.current_max_speed,
            'status': "STANDBY",
            'fps': 0,
            'track_active': False,
            'stab_active': self.digital_stabilization_active,
            'recording': False # Added recording status
        }
        
        # Manual Control Request
        self.manual_cmd = {'pan': 0, 'tilt': 0, 'zoom': 0, 'timestamp': 0}

    def start(self):
        if self.running: return
        self.running = True
        
        # Initialize Hardware
        self.ptz.stop()
        self.ptz.start_polling(interval=0.2)
        self.video = ThreadedVideoCapture(config.RTSP_URL).start()
        
        # Start Loop
        # Start Loop
        self.thread = threading.Thread(target=self._safe_update_loop, daemon=True)
        self.thread.start()
        print("SkyWatch Core Started.")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
        if self.ptz:
            self.ptz.stop()
            self.ptz.stop_polling()
        if self.video:
            self.video.stop()
        # Ensure video writer is released on stop
        if self.video_writer:
            self.video_writer.release()
            self.video_writer = None
        print("SkyWatch Core Stopped.")

    def set_manual_command(self, pan, tilt, zoom):
        with self.lock:
            self.manual_cmd = {
                'pan': pan, 
                'tilt': tilt, 
                'zoom': zoom, 
                'timestamp': time.time()
            }
            # If we receive a manual command, tracking disengages automatically?
            # Or we handle manual override in the loop.
            # Usually, manual input should override tracking.
            if (pan != 0 or tilt != 0 or zoom != 0) and self.tracking_active:
                self.stop_tracking()

    def toggle_tracking(self):
        with self.lock:
            if self.tracking_active:
                self.stop_tracking()
            else:
                self.start_tracking()

    def start_tracking(self):
        self.tracking_active = True
        # Reset PID
        # Reset PID
        for k in self.pid_state:
            if k not in ['last_sent_pan', 'last_sent_tilt', 'last_visca_time']:
                self.pid_state[k] = 0
        self.kf = None
        self.tracker = None 
        # Note: Actual tracker initialization happens in the loop when we have a frame
        # We need a flag to tell the loop "Please Initialize Tracker on Center"
        self.init_tracker_requested = True

    def stop_tracking(self):
        self.tracking_active = False
        self.ptz.stop()
        self.tracker = None
        self.kf = None

    def toggle_stabilization(self):
        self.digital_stabilization_active = not self.digital_stabilization_active

    def set_pid(self, p, i, d):
        self.current_kp = p
        self.current_ki = i
        self.current_kd = d

    def set_max_speed(self, speed):
        self.current_max_speed = speed

    def get_frame(self):
        with self.lock:
            if self.latest_frame is None:
                return None
            return self.latest_frame.copy()

    def get_telemetry_data(self):
        with self.lock:
            return self.telemetry.copy()

    def _get_dynamic_max_speed(self, error_dist):
        # ... logic from main.py ...
        prev_dist = 0
        prev_speed = 0.0
        for threshold, limit in config.DYNAMIC_SPEED_RANGES:
            if error_dist <= threshold:
                ratio = (error_dist - prev_dist) / (threshold - prev_dist)
                return prev_speed + ratio * (limit - prev_speed)
            prev_dist = threshold
            prev_speed = limit
        
        max_dist = 600
        if error_dist >= max_dist:
             return config.MAX_PAN_SPEED
        ratio = (error_dist - prev_dist) / (max_dist - prev_dist)
        return prev_speed + ratio * (config.MAX_PAN_SPEED - prev_speed)


    def toggle_recording(self):
        with self.lock:
            if not self.recording:
                # Start Recording
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = os.path.join(self.download_dir, f"skywatch_rec_{timestamp}.mp4")
                # Define codec - try mp4v (widely supported) or avc1
                fourcc = cv2.VideoWriter_fourcc(*'mp4v') 
                # Frame size must match input. Assuming 1920x1080 from config/camera
                # Ideally get actual frame size, but config says WIDTH/HEIGHT
                self.video_writer = cv2.VideoWriter(filename, fourcc, 30.0, (config.CAMERA_WIDTH, config.CAMERA_HEIGHT))
                if self.video_writer.isOpened():
                    self.recording = True
                    print(f"Recording started: {filename}")
                else:
                    print("Failed to start recording")
            else:
                # Stop Recording
                self.recording = False
                if self.video_writer:
                    self.video_writer.release()
                    self.video_writer = None
                print("Recording stopped")

            self.telemetry['recording'] = self.recording

    def _safe_update_loop(self):
        try:
            self._update_loop()
        except Exception as e:
            print(f"CRITICAL ERROR IN CORE LOOP: {e}")
            traceback.print_exc()
            with self.lock:
                self.telemetry['status'] = f"ERR: {str(e)}"
            self.running = False

    def _update_loop(self):
        prev_time = time.time()
        # Wait for camera
        time.sleep(1.0)
        
        while self.running:
            loop_start = time.time()
            
            # 1. Capture
            frame = self.video.read()
            if frame is None:
                time.sleep(0.01)
                continue
                
            display_frame = frame.copy()
            h, w = frame.shape[:2]
            center_x = w // 2
            center_y = h // 2
            
            current_time = time.time()
            dt = current_time - prev_time
            if dt == 0: dt = 0.001
            prev_time = current_time

            # 2. Tracking Update
            cur_obj_center_x = None
            cur_obj_center_y = None
            
            # Tracker Init (Requested via Web/API)
            if getattr(self, 'init_tracker_requested', False):
                half = config.RETICLE_SIZE // 2
                rx1, ry1 = center_x - half, center_y - half
                self.tracker = cv2.TrackerCSRT_create()
                self.tracker.init(frame, (rx1, ry1, config.RETICLE_SIZE, config.RETICLE_SIZE))
                self.tracking_active = True
                self.init_tracker_requested = False
                self.kf = None

            if self.tracking_active and self.tracker:
                success, box = self.tracker.update(frame)
                if not success:
                    # Tracker Lost
                    # self.tracking_active = False # Optional: Auto-disengage?
                    # self.ptz.stop()
                    pass
                else:
                    x, y, w_box, h_box = [int(v) for v in box]
                    cur_obj_center_x = x + w_box // 2
                    cur_obj_center_y = y + h_box // 2
                    
                    if self.kf is None:
                         self.kf = SkyWatchKalman(cur_obj_center_x, cur_obj_center_y, 
                                           process_noise=config.KF_PROCESS_NOISE, 
                                           measurement_noise=config.KF_MEASUREMENT_NOISE)
                    
                    self.kf.predict(dt + config.SYSTEM_LATENCY)
                    kf_x, kf_y, kf_vx, kf_vy = self.kf.update(cur_obj_center_x, cur_obj_center_y)
                    
                    # PID Calc
                    error_x = center_x - kf_x
                    error_y = center_y - kf_y
                    
                    # ... PID Logic (copied/adapted from main.py) ...
                    # Using self.pid_state dictionary
                    
                    dynamic_limit = self._get_dynamic_max_speed(max(abs(error_x), abs(error_y)))
                    active_max_speed = min(self.current_max_speed, dynamic_limit)

                    if abs(error_x) > config.DEADBAND:
                        self.pid_state['error_sum_x'] += error_x * dt
                    if abs(error_y) > config.DEADBAND:
                        self.pid_state['error_sum_y'] += error_y * dt
                        
                    # Anti-Windup
                    max_i = config.INTEGRAL_MAX / self.current_ki if self.current_ki > 0 else 0
                    if max_i > 0:
                        self.pid_state['error_sum_x'] = max(min(self.pid_state['error_sum_x'], max_i), -max_i)
                        self.pid_state['error_sum_y'] = max(min(self.pid_state['error_sum_y'], max_i), -max_i)

                    p_x = self.current_kp * error_x
                    p_y = self.current_kp * error_y
                    i_x = self.current_ki * self.pid_state['error_sum_x']
                    i_y = self.current_ki * self.pid_state['error_sum_y']
                    d_x = (error_x - self.pid_state['prev_error_x']) / dt
                    d_y = (error_y - self.pid_state['prev_error_y']) / dt
                    
                    pid_pan = p_x + i_x + self.current_kd * d_x
                    pid_tilt = p_y + i_y + self.current_kd * d_y
                    
                    ff_pan = kf_vx * config.FEED_FORWARD_GAIN
                    ff_tilt = kf_vy * config.FEED_FORWARD_GAIN
                    
                    if config.PAN_INVERT: pid_pan, ff_pan = -pid_pan, -ff_pan
                    if config.TILT_INVERT: pid_tilt, ff_tilt = -pid_tilt, -ff_tilt
                    
                    if abs(error_x) < config.DEADBAND: pid_pan = 0
                    if abs(error_y) < config.DEADBAND: pid_tilt = 0
                    
                    target_pan = pid_pan + ff_pan
                    target_tilt = pid_tilt + ff_tilt
                    
                    self.pid_state['prev_error_x'] = error_x
                    self.pid_state['prev_error_y'] = error_y
                    
                    # Smoothing
                    pan_speed_f = config.SPEED_SMOOTHING * target_pan + (1 - config.SPEED_SMOOTHING) * self.pid_state['prev_pan_speed']
                    tilt_speed_f = config.SPEED_SMOOTHING * target_tilt + (1 - config.SPEED_SMOOTHING) * self.pid_state['prev_tilt_speed']
                    self.pid_state['prev_pan_speed'] = pan_speed_f
                    self.pid_state['prev_tilt_speed'] = tilt_speed_f
                    
                    # Clamp
                    pan_speed_f = max(min(pan_speed_f, active_max_speed), -active_max_speed)
                    tilt_speed_f = max(min(tilt_speed_f, active_max_speed), -active_max_speed)
                    
                    # Accumulator
                    self.pid_state['pan_accumulator'] += pan_speed_f
                    self.pid_state['tilt_accumulator'] += tilt_speed_f
                    pan_speed = int(self.pid_state['pan_accumulator'])
                    tilt_speed = int(self.pid_state['tilt_accumulator'])
                    self.pid_state['pan_accumulator'] -= pan_speed
                    self.pid_state['tilt_accumulator'] -= tilt_speed
                    
                    # Min Check
                    if pan_speed != 0 and abs(pan_speed) < config.MIN_PAN_SPEED:
                        pan_speed = config.MIN_PAN_SPEED if pan_speed > 0 else -config.MIN_PAN_SPEED
                    if tilt_speed != 0 and abs(tilt_speed) < config.MIN_TILT_SPEED:
                        tilt_speed = config.MIN_TILT_SPEED if tilt_speed > 0 else -config.MIN_TILT_SPEED
                        
                    # Send
                    current_time_visca = time.time()
                    should_send = False
                    if (pan_speed == 0 and self.pid_state['last_sent_pan'] != 0) or (tilt_speed == 0 and self.pid_state['last_sent_tilt'] != 0):
                         should_send = True
                    elif abs(pan_speed - self.pid_state['last_sent_pan']) > 2 or abs(tilt_speed - self.pid_state['last_sent_tilt']) > 2:
                         should_send = True
                    elif current_time_visca - self.pid_state['last_visca_time'] > 0.1:
                         should_send = True
                         
                    if should_send:
                        if abs(pan_speed) > 0 or abs(tilt_speed) > 0:
                            self.ptz.pan_tilt(pan_speed, tilt_speed)
                        else:
                            self.ptz.stop()
                            self.pid_state['pan_accumulator'] = 0.0
                            self.pid_state['tilt_accumulator'] = 0.0
                        self.pid_state['last_visca_time'] = current_time_visca
                        self.pid_state['last_sent_pan'] = pan_speed
                        self.pid_state['last_sent_tilt'] = tilt_speed

            # Manual Control
            if not self.tracking_active:
                # Check for manual commands
                 # Simplified Manual Logic for now
                 # manual_cmd format: {'pan': 0, 'tilt': 0, 'zoom': 0, 'timestamp': ts}
                 # We need to stop if timestamp is old
                 if time.time() - self.manual_cmd['timestamp'] < 0.25: # 250ms Keep-Alive
                     self.manual_mode_active = True
                     
                     m_pan = self.manual_cmd['pan']
                     m_tilt = self.manual_cmd['tilt']
                     m_zoom = self.manual_cmd['zoom']
                     
                     if config.PAN_INVERT: m_pan = -m_pan
                     if config.TILT_INVERT: m_tilt = -m_tilt
                     
                     if m_zoom != 0:
                         self.ptz.zoom(m_zoom)
                     else:
                         self.ptz.zoom(0) # Stop zoom? Or just don't send? 
                         # Note: ptz.zoom usually requires constant send? Unclear from snippet.
                         # Assuming we need to stop zoom if 0
                         # But pan_tilt handles its own stopping.
                     
                     if m_pan != 0 or m_tilt != 0:
                         self.ptz.pan_tilt(m_pan, m_tilt)
                 else:
                     if self.manual_mode_active:
                         self.ptz.stop()
                         self.manual_mode_active = False

            # 3. Stabilization / Display Prep
            if self.digital_stabilization_active:
                crop_h = int(h * config.DIGITAL_CROP_FACTOR)
                crop_w = int(w * config.DIGITAL_CROP_FACTOR)
                
                if self.tracking_active and cur_obj_center_x is not None:
                     target_x = cur_obj_center_x
                     target_y = cur_obj_center_y
                     crop_x1 = int(target_x - crop_w // 2)
                     crop_y1 = int(target_y - crop_h // 2)
                else:
                     crop_x1 = (w - crop_w) // 2
                     crop_y1 = (h - crop_h) // 2
                     
                crop_x2 = crop_x1 + crop_w
                crop_y2 = crop_y1 + crop_h
                
                # Padding Logic
                cropped_frame = np.zeros((crop_h, crop_w, 3), dtype=np.uint8)
                src_x1 = max(0, crop_x1)
                src_y1 = max(0, crop_y1)
                src_x2 = min(w, crop_x2)
                src_y2 = min(h, crop_y2)
                
                dst_x1 = src_x1 - crop_x1
                dst_y1 = src_y1 - crop_y1
                dst_x2 = dst_x1 + (src_x2 - src_x1)
                dst_y2 = dst_y1 + (src_y2 - src_y1)
                
                if src_x2 > src_x1 and src_y2 > src_y1:
                    cropped_frame[dst_y1:dst_y2, dst_x1:dst_x2] = frame[src_y1:src_y2, src_x1:src_x2]
                
                display_frame = cv2.resize(cropped_frame, (w, h), interpolation=cv2.INTER_LINEAR)
            
            # Overlay Blending
            if self.overlay is not None:
                oh, ow = self.overlay.shape[:2]
                # Resize overlay if needed or just clip? Main.py checked if oh <= h
                if oh <= h and ow <= w:
                    if self.overlay.shape[2] == 4:
                        alpha_channel = self.overlay[:, :, 3]
                        overlay_bgr = self.overlay[:, :, :3]
                        mask = alpha_channel > 0
                        display_frame[0:oh, 0:ow][mask] = overlay_bgr[mask]

            # Draw OSD (Shapes Only - Burned In)
            if self.tracking_active and cur_obj_center_x is not None:
                if self.digital_stabilization_active:
                    scale_x = w / crop_w
                    scale_y = h / crop_h
                    disp_x = int((x - crop_x1) * scale_x)
                    disp_y = int((y - crop_y1) * scale_y)
                    disp_w = int(w_box * scale_x)
                    disp_h = int(h_box * scale_y)
                    draw_rect(display_frame, (disp_x, disp_y), (disp_x + disp_w, disp_y + disp_h), (255, 255, 255), 1)
                    
                    disp_kf_x = int((kf_x - crop_x1) * scale_x)
                    disp_kf_y = int((kf_y - crop_y1) * scale_y)
                    draw_circle(display_frame, (disp_kf_x, disp_kf_y), 2, (255, 255, 255), -1)
                else:
                    draw_rect(display_frame, (x, y), (x + w_box, y + h_box), (255, 255, 255), 1)
                    draw_circle(display_frame, (int(kf_x), int(kf_y)), 2, (255, 255, 255), -1)
            else:
                 # Manual Reticle
                 half_size = config.RETICLE_SIZE // 2
                 draw_line(display_frame, (center_x - 20, center_y), (center_x + 20, center_y), (255, 255, 255), 1)
                 draw_line(display_frame, (center_x, center_y - 20), (center_x, center_y + 20), (255, 255, 255), 1)

            # Update Telemetry (Thread Safe)
            with self.lock:
                self.latest_frame = display_frame
                
                # --- Recording ---
                if self.recording and self.video_writer:
                    # Write the frame (stabilized or raw? User usually wants what they see, or raw?)
                    # If digital stab is on, 'frame' is stabilized/cropped?
                    # Let's write the 'display_frame' variable which is currently displayed.
                    # Note: If 'display_frame' size changed due to stabilization (resize?), video writer might fail if size mismatch.
                    # Our stabilization logic ensures output is resized back to CAMERA_WIDTH/HEIGHT.
                    self.video_writer.write(display_frame) # Changed to display_frame

                z_pos, p_pos, t_pos = self.ptz.get_cached_pos()
                
                # Update Telemetry Dict
                self.telemetry['track_active'] = self.tracking_active
                self.telemetry['stab_active'] = self.digital_stabilization_active # Corrected to digital_stabilization_active
                self.telemetry['kp'] = self.current_kp
                self.telemetry['ki'] = self.current_ki
                self.telemetry['kd'] = self.current_kd
                self.telemetry['speed_limit'] = self.current_max_speed
                self.telemetry['status'] = "TRACKING" if self.tracking_active else ("MANUAL" if self.manual_mode_active else "STANDBY")
                self.telemetry['recording'] = self.recording # Added recording status
                
                if p_pos is not None:
                     p_signed = p_pos
                     if p_signed > 0x7FFF: p_signed -= 0x10000
                     self.telemetry['pan'] = p_signed / config.PAN_COUNTS_PER_DEGREE
                
                if t_pos is not None:
                     t_signed = t_pos
                     if t_signed > 0x7FFF: t_signed -= 0x10000
                     self.telemetry['tilt'] = t_signed / config.TILT_COUNTS_PER_DEGREE

                if z_pos is not None:
                     self.telemetry['zoom'] = 1.0 + (z_pos / config.ZOOM_MAX_HEX) * (config.ZOOM_MAX_X - 1.0)
