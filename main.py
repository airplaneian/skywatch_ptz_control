import cv2
import numpy as np
import math
import time
from datetime import datetime, timezone
import config
from video_capture import ThreadedVideoCapture
from visca_control import CameraControl
from kalman_filter import SkyWatchKalman

# --- OSD Drawing Helpers ---
def draw_text(img, text, pos, font, scale, color, thickness=1):
    # Black outline
    cv2.putText(img, text, pos, font, scale, (0, 0, 0), thickness + 2, cv2.LINE_AA)
    # Colored text
    cv2.putText(img, text, pos, font, scale, color, thickness, cv2.LINE_AA)

def draw_line(img, pt1, pt2, color, thickness=1):
    cv2.line(img, pt1, pt2, (0, 0, 0), thickness + 2, cv2.LINE_AA)
    cv2.line(img, pt1, pt2, color, thickness, cv2.LINE_AA)

def draw_rect(img, pt1, pt2, color, thickness=1):
    cv2.rectangle(img, pt1, pt2, (0, 0, 0), thickness + 2, cv2.LINE_AA)
    cv2.rectangle(img, pt1, pt2, color, thickness, cv2.LINE_AA)

def draw_circle(img, center, radius, color, thickness=1):
    if thickness == -1:
        # Filled circle: Draw filled color, then black outline
        cv2.circle(img, center, radius, color, -1, cv2.LINE_AA)
        cv2.circle(img, center, radius, (0, 0, 0), 1, cv2.LINE_AA)
    else:
        # Stroke circle
        cv2.circle(img, center, radius, (0, 0, 0), thickness + 2, cv2.LINE_AA)
        cv2.circle(img, center, radius, color, thickness, cv2.LINE_AA)

def draw_ellipse(img, center, axes, angle, startAngle, endAngle, color, thickness=1):
    cv2.ellipse(img, center, axes, angle, startAngle, endAngle, (0, 0, 0), thickness + 2, cv2.LINE_AA)
    cv2.ellipse(img, center, axes, angle, startAngle, endAngle, color, thickness, cv2.LINE_AA)

def draw_poly_filled(img, pts, color):
    # Draw filled
    cv2.drawContours(img, [pts], 0, color, -1, cv2.LINE_AA)
    # Draw outline
    cv2.drawContours(img, [pts], 0, (0, 0, 0), 1, cv2.LINE_AA)

def main():
    # Initialize Camera Control
    print("Initializing VISCA Control...")
    ptz = CameraControl(config.CAMERA_IP, config.VISCA_PORT)
    # Ensure camera is stopped initially
    ptz.stop()
    # Start Polling
    ptz.start_polling(interval=0.2)

    # Initialize Video Capture
    print(f"Connecting to RTSP Stream: {config.RTSP_URL}")
    video = ThreadedVideoCapture(config.RTSP_URL).start()

    # Wait for first frame
    time.sleep(1.0)
    if video.read() is None:
        print("Warning: No video feed detected. Check IP/Network.")

    # Load Overlay
    try:
        overlay = cv2.imread(config.OVERLAY_IMAGE_PATH, cv2.IMREAD_UNCHANGED)
        if overlay is None:
            print("Warning: Overlay image found but could not be loaded.")
    except Exception as e:
        print(f"Warning: Could not load overlay: {e}")
        overlay = None

    # Tracker Setup
    tracker = None
    tracking_active = False
    kf = None # Kalman Filter Instance
    
    # PID State
    prev_error_x = 0
    prev_error_y = 0
    error_sum_x = 0.0
    error_sum_y = 0.0
    prev_pan_speed = 0.0
    prev_pan_speed = 0.0
    prev_tilt_speed = 0.0
    
    # Sub-Integer Speed Accumulators
    pan_accumulator = 0.0
    tilt_accumulator = 0.0
    
    # VISCA State
    last_visca_time = 0
    last_sent_pan = 0
    last_sent_tilt = 0
    
    # OSD State
    last_poll_time = 0
    cam_zoom_str = "---"
    cam_az_str = "---"
    cam_el_str = "---"
    last_pan_val = -1
    last_tilt_val = -1
    JITTER_THRESHOLD = 3
    prev_time = time.time()
    
    # Manual Control State
    manual_mode_active = False
    last_manual_time = 0
    MANUAL_TIMEOUT = 0.2 # Seconds before stopping if no key pressed
    
    # Dynamic Speed Control
    current_max_speed = config.MAX_PAN_SPEED
    
    # Digital Stabilization State
    digital_stabilization_active = config.DIGITAL_STABILIZATION_ENABLED
    
    # Dynamic PID Control
    current_kp = config.PAN_KP
    current_ki = config.PAN_KI
    current_kd = config.PAN_KD

    # Window Setup
    window_name = "SkyWatch PTZ Control"
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
    cv2.moveWindow(window_name, 50, 50) # Top-left of primary screen with offset

    print("Controls:")
    print("  MANUAL MODE: Steer camera to center object in the box.")
    print("    WASD: Pan/Tilt manually.")
    print("    Q/E: Adjust Max Speed.")
    print("    1-6: Tune PID (P:1/2, I:3/4, D:5/6).")
    print("    Z: Toggle Digital Stabilization.")
    print("  SPACE: Lock/Unlock tracking on center object.")
    print("  ESC: Quit.")

    # Helper for Dynamic Speed
    def get_dynamic_max_speed(error_dist):
        # Define start point (0 distance = 0 speed)
        prev_dist = 0
        prev_speed = 0.0
        
        for threshold, limit in config.DYNAMIC_SPEED_RANGES:
            if error_dist <= threshold:
                # Interpolate
                ratio = (error_dist - prev_dist) / (threshold - prev_dist)
                return prev_speed + ratio * (limit - prev_speed)
            
            # Update previous point for next iteration
            prev_dist = threshold
            prev_speed = limit
            
        # If we are here, we are beyond the last threshold (300px, speed 3.0)
        # We want to reach MAX_PAN_SPEED (5.0) eventually.
        # Let's say we reach max speed at 600px?
        max_dist = 600
        if error_dist >= max_dist:
            return config.MAX_PAN_SPEED
        
        # Interpolate from last point to max speed
        ratio = (error_dist - prev_dist) / (max_dist - prev_dist)
        return prev_speed + ratio * (config.MAX_PAN_SPEED - prev_speed)

    # Main Loop
    try:
        while True:
            loop_start_time = time.time()
            
            # Read Frame
            frame = video.read()
            if frame is None:
                # If no frame, wait a bit and try again
                time.sleep(0.01)
                continue
                
            # Resize for display/processing (optional, but good for performance)
            # frame = cv2.resize(frame, (1280, 720)) 
            
            display_frame = frame.copy()
            h, w = frame.shape[:2]
            center_x = w // 2
            center_y = h // 2
            
            current_time = time.time()
            dt = current_time - prev_time
            if dt == 0: dt = 0.001 # Avoid divide by zero
            prev_time = current_time

            # --- Tracking Logic (Update & Control) ---
            # We must update tracking BEFORE stabilization to use the current frame's data
            
            # Initialize tracking vars for this frame
            cur_obj_center_x = None
            cur_obj_center_y = None
            
            if tracking_active:
                # IMPORTANT: Tracker updates on the RAW frame
                success, box = tracker.update(frame)
                
                if not success:
                    tracking_active = False
                    ptz.stop()
                    # If lost, we fall through to stabilization (which will use center crop)
                else:
                    x, y, w_box, h_box = [int(v) for v in box]
                    
                    # Calculate Raw Center
                    cur_obj_center_x = x + w_box // 2
                    cur_obj_center_y = y + h_box // 2
                    
                    # Initialize Kalman Filter if needed
                    if kf is None:
                        kf = SkyWatchKalman(cur_obj_center_x, cur_obj_center_y, 
                                          process_noise=config.KF_PROCESS_NOISE, 
                                          measurement_noise=config.KF_MEASUREMENT_NOISE)
                    
                    # Kalman Filter Update
                    kf.predict(dt + config.SYSTEM_LATENCY)
                    kf_x, kf_y, kf_vx, kf_vy = kf.update(cur_obj_center_x, cur_obj_center_y)
                    
                    # Calculate Error based on FILTERED position (for PTZ Control)
                    error_x = center_x - kf_x
                    error_y = center_y - kf_y
                    
                    # --- PTZ Control Logic (PID + FF) ---
                    # (Moved here from below)
                    
                    # Dynamic Speed Limit Calculation
                    max_error = max(abs(error_x), abs(error_y))
                    dynamic_limit = get_dynamic_max_speed(max_error)
                    active_max_speed = min(current_max_speed, dynamic_limit)
                    
                    # Update Integral
                    if abs(error_x) > config.DEADBAND:
                        error_sum_x += error_x * dt
                    if abs(error_y) > config.DEADBAND:
                        error_sum_y += error_y * dt
                    
                    # Anti-Windup
                    max_i_x = config.INTEGRAL_MAX / current_ki if current_ki > 0 else 0
                    max_i_y = config.INTEGRAL_MAX / current_ki if current_ki > 0 else 0
                    if max_i_x > 0: error_sum_x = max(min(error_sum_x, max_i_x), -max_i_x)
                    if max_i_y > 0: error_sum_y = max(min(error_sum_y, max_i_y), -max_i_y)

                    # PID Calculation
                    p_x = current_kp * error_x
                    p_y = current_kp * error_y
                    i_x = current_ki * error_sum_x
                    i_y = current_ki * error_sum_y
                    d_x = (error_x - prev_error_x) / dt
                    d_y = (error_y - prev_error_y) / dt
                    d_term_x = current_kd * d_x
                    d_term_y = current_kd * d_y
                    
                    pid_pan_speed = p_x + i_x + d_term_x
                    pid_tilt_speed = p_y + i_y + d_term_y
                    
                    # Feed Forward
                    ff_pan_speed = kf_vx * config.FEED_FORWARD_GAIN
                    ff_tilt_speed = kf_vy * config.FEED_FORWARD_GAIN
                    
                    # Invert Logic
                    if config.PAN_INVERT: 
                        pid_pan_speed = -pid_pan_speed
                        ff_pan_speed = -ff_pan_speed
                    if config.TILT_INVERT: 
                        pid_tilt_speed = -pid_tilt_speed
                        ff_tilt_speed = -ff_tilt_speed
                        
                    # Deadband
                    if abs(error_x) < config.DEADBAND: pid_pan_speed = 0
                    if abs(error_y) < config.DEADBAND: pid_tilt_speed = 0
                    
                    # Combine
                    target_pan_speed = pid_pan_speed + ff_pan_speed
                    target_tilt_speed = pid_tilt_speed + ff_tilt_speed
                    
                    # Update State
                    prev_error_x = error_x
                    prev_error_y = error_y
                    
                    # Smoothing
                    pan_speed_f = config.SPEED_SMOOTHING * target_pan_speed + (1 - config.SPEED_SMOOTHING) * prev_pan_speed
                    tilt_speed_f = config.SPEED_SMOOTHING * target_tilt_speed + (1 - config.SPEED_SMOOTHING) * prev_tilt_speed
                    prev_pan_speed = pan_speed_f
                    prev_tilt_speed = tilt_speed_f
                    
                    # Clamp
                    pan_speed_f = max(min(pan_speed_f, active_max_speed), -active_max_speed)
                    tilt_speed_f = max(min(tilt_speed_f, active_max_speed), -active_max_speed)
                    
                    # Accumulator
                    pan_accumulator += pan_speed_f
                    tilt_accumulator += tilt_speed_f
                    pan_speed = int(pan_accumulator)
                    tilt_speed = int(tilt_accumulator)
                    pan_accumulator -= pan_speed
                    tilt_accumulator -= tilt_speed
                    
                    # Min Speed Check
                    if pan_speed != 0 and abs(pan_speed) < config.MIN_PAN_SPEED:
                         pan_speed = config.MIN_PAN_SPEED if pan_speed > 0 else -config.MIN_PAN_SPEED
                    if tilt_speed != 0 and abs(tilt_speed) < config.MIN_TILT_SPEED:
                         tilt_speed = config.MIN_TILT_SPEED if tilt_speed > 0 else -config.MIN_TILT_SPEED

                    # Send VISCA
                    current_time_visca = time.time()
                    should_send = False
                    if (pan_speed == 0 and last_sent_pan != 0) or (tilt_speed == 0 and last_sent_tilt != 0):
                         should_send = True
                    elif abs(pan_speed - last_sent_pan) > 2 or abs(tilt_speed - last_sent_tilt) > 2:
                         should_send = True
                    elif current_time_visca - last_visca_time > 0.1:
                         should_send = True
                    
                    if should_send:
                        if abs(pan_speed) > 0 or abs(tilt_speed) > 0:
                            ptz.pan_tilt(pan_speed, tilt_speed)
                        else:
                            ptz.stop()
                            pan_accumulator = 0.0
                            tilt_accumulator = 0.0
                        last_visca_time = current_time_visca
                        last_sent_pan = pan_speed
                        last_sent_tilt = tilt_speed

            # --- Digital Stabilization Logic ---
            if digital_stabilization_active:
                crop_h = int(h * config.DIGITAL_CROP_FACTOR)
                crop_w = int(w * config.DIGITAL_CROP_FACTOR)
                
                if tracking_active and cur_obj_center_x is not None:
                    # Use RAW position (cur_obj_center_x) for "Locked On" feel
                    target_x = cur_obj_center_x
                    target_y = cur_obj_center_y
                    
                    # Do NOT clamp the center. Allow it to go wherever.
                    # Calculate ideal crop coordinates
                    crop_x1 = int(target_x - crop_w // 2)
                    crop_y1 = int(target_y - crop_h // 2)
                else:
                    # Default to center crop
                    crop_x1 = (w - crop_w) // 2
                    crop_y1 = (h - crop_h) // 2
                
                crop_x2 = crop_x1 + crop_w
                crop_y2 = crop_y1 + crop_h
                
                # Handle Out-of-Bounds with Padding (Black Bars)
                # 1. Create black canvas
                cropped_frame = np.zeros((crop_h, crop_w, 3), dtype=np.uint8)
                
                # 2. Calculate intersection with actual frame
                # Frame coords: 0,0 to w,h
                # Crop coords: crop_x1,crop_y1 to crop_x2,crop_y2
                
                src_x1 = max(0, crop_x1)
                src_y1 = max(0, crop_y1)
                src_x2 = min(w, crop_x2)
                src_y2 = min(h, crop_y2)
                
                # 3. Calculate placement on canvas
                dst_x1 = src_x1 - crop_x1
                dst_y1 = src_y1 - crop_y1
                dst_x2 = dst_x1 + (src_x2 - src_x1)
                dst_y2 = dst_y1 + (src_y2 - src_y1)
                
                # 4. Copy valid region if it exists
                if src_x2 > src_x1 and src_y2 > src_y1:
                    cropped_frame[dst_y1:dst_y2, dst_x1:dst_x2] = frame[src_y1:src_y2, src_x1:src_x2]
                
                display_frame = cv2.resize(cropped_frame, (w, h), interpolation=cv2.INTER_LINEAR)
            else:
                display_frame = frame.copy()

            # Overlay Blending
            if overlay is not None:
                oh, ow = overlay.shape[:2]
                if oh <= h and ow <= w:
                    if overlay.shape[2] == 4:
                        alpha_channel = overlay[:, :, 3]
                        overlay_bgr = overlay[:, :, :3]
                        mask = alpha_channel > 0
                        display_frame[0:oh, 0:ow][mask] = overlay_bgr[mask]
            
            # --- Drawing Logic (Boxes & Reticles) ---
            if tracking_active and cur_obj_center_x is not None:
                # Draw Bounding Box
                if digital_stabilization_active:
                    scale_x = w / crop_w
                    scale_y = h / crop_h
                    disp_x = int((x - crop_x1) * scale_x)
                    disp_y = int((y - crop_y1) * scale_y)
                    disp_w = int(w_box * scale_x)
                    disp_h = int(h_box * scale_y)
                    draw_rect(display_frame, (disp_x, disp_y), (disp_x + disp_w, disp_y + disp_h), (255, 255, 255), 1)
                    
                    # Draw Filtered Center (White Dot) - mapped
                    disp_kf_x = int((kf_x - crop_x1) * scale_x)
                    disp_kf_y = int((kf_y - crop_y1) * scale_y)
                    draw_circle(display_frame, (disp_kf_x, disp_kf_y), 2, (255, 255, 255), -1)
                else:
                    draw_rect(display_frame, (x, y), (x + w_box, y + h_box), (255, 255, 255), 1)
                    draw_circle(display_frame, (int(kf_x), int(kf_y)), 2, (255, 255, 255), -1)
                
            else:
                # Manual Mode - Draw Reticle
                # Define Center Box
                half_size = config.RETICLE_SIZE // 2
                rx1 = center_x - half_size
                ry1 = center_y - half_size
                rx2 = center_x + half_size
                ry2 = center_y + half_size
                
                # Ensure bounds
                rx1 = max(0, rx1); ry1 = max(0, ry1)
                rx2 = min(w, rx2); ry2 = min(h, ry2)
                
                # Static Reticle
                color = (255, 255, 255) # White
                
                # Draw Reticle
                # Corners only or full box? User requested NO BOX in manual mode.
                # cv2.rectangle(display_frame, (rx1, ry1), (rx2, ry2), color, 2)
                    
                # Crosshair
                # Crosshair - Manually layered to avoid outline overlap
                # Draw outlines (Background)
                cv2.line(display_frame, (center_x - 20, center_y), (center_x + 20, center_y), (0, 0, 0), 3, cv2.LINE_AA)
                cv2.line(display_frame, (center_x, center_y - 20), (center_x, center_y + 20), (0, 0, 0), 3, cv2.LINE_AA)
                # Draw foreground (White)
                cv2.line(display_frame, (center_x - 20, center_y), (center_x + 20, center_y), color, 1, cv2.LINE_AA)
                cv2.line(display_frame, (center_x, center_y - 20), (center_x, center_y + 20), color, 1, cv2.LINE_AA)
                
            # --- OSD (On Screen Display) ---            
            # Status Logic & Color
            osd_status_color = (255, 255, 255) # Default White
            
            if tracking_active:
                if success:
                    # Blinking Logic Removed - Solid Red
                    status_text = "TRK ACT"
                    osd_status_color = (0, 0, 255) # Red
                else:
                    status_text = "[ LOST ]"
                    osd_status_color = (0, 0, 255) # Red
            else:
                status_text = "TRK STBY"
                osd_status_color = (255, 255, 255)

            # Update OSD strings from cache every frame
            z_pos, p_pos, t_pos = ptz.get_cached_pos()
            
            if z_pos is not None:
                zoom_factor = 1.0 + (z_pos / config.ZOOM_MAX_HEX) * (config.ZOOM_MAX_X - 1.0)
                cam_zoom_str = f"{zoom_factor:.1f}X"
            
            if p_pos is not None and t_pos is not None:
                # Jitter Filter
                if last_pan_val == -1 or abs(int(p_pos) - last_pan_val) > JITTER_THRESHOLD:
                    last_pan_val = int(p_pos)
                    p_signed = p_pos
                    if p_signed > 0x7FFF: p_signed -= 0x10000
                    pan_deg = p_signed / config.PAN_COUNTS_PER_DEGREE
                    cam_az_str = f"{pan_deg:03.0f} DEG" 

                if last_tilt_val == -1 or abs(int(t_pos) - last_tilt_val) > JITTER_THRESHOLD:
                    last_tilt_val = int(t_pos)
                    t_signed = t_pos
                    if t_signed > 0x7FFF: t_signed -= 0x10000
                    tilt_deg = t_signed / config.TILT_COUNTS_PER_DEGREE
                    cam_el_str = f"{tilt_deg:+03.0f} DEG"
            
            # --- Simple OpenCV OSD (Lower Left) ---
            # Display Max Speed, PID, and Keybinds
            osd_color = (255, 255, 255)
            font = cv2.FONT_HERSHEY_PLAIN
            font_scale = 1.5 
            thickness = 2
            line_height = 25
            
            # --- Top Left OSD ---
            tl_start_x = 20
            tl_start_y = 30
            
            # 1. Static Text
            draw_text(display_frame, "AIRPLANE IAN SYSTEMS 401", (tl_start_x, tl_start_y), font, font_scale, osd_color, thickness)
            
            # 2. Date
            now = datetime.now()
            date_str = now.strftime("%m/%d/%Y")
            draw_text(display_frame, date_str, (tl_start_x, tl_start_y + line_height), font, font_scale, osd_color, thickness)
            
            # 3. UTC Time
            utc_now = datetime.now(timezone.utc)
            utc_str = utc_now.strftime("%H:%M:%S Z")
            draw_text(display_frame, utc_str, (tl_start_x, tl_start_y + line_height * 2), font, font_scale, osd_color, thickness)
            
            # 4. Local Time
            local_str = now.strftime("%H:%M:%S LCL")
            draw_text(display_frame, local_str, (tl_start_x, tl_start_y + line_height * 3), font, font_scale, osd_color, thickness)



            start_x = 20
            start_y = h - 60
            
            # New Static Lines (Stacked above Max Speed)
            draw_text(display_frame, "HDEO", (start_x, start_y - line_height * 3), font, font_scale, osd_color, thickness)
            draw_text(display_frame, "FOC MAN", (start_x, start_y - line_height * 2), font, font_scale, osd_color, thickness)
            draw_text(display_frame, "EXP AUT", (start_x, start_y - line_height * 1), font, font_scale, osd_color, thickness)
            
            # 1. Max Speed
            # Show both Global Setting and Current Dynamic Limit
            if tracking_active and 'active_max_speed' in locals():
                 speed_str = f"MAX SPD {active_max_speed:.2f} (DYN) / {current_max_speed:.2f} (SET)"
            else:
                 speed_str = f"MAX SPD {current_max_speed:.2f} (SET)"
            
            draw_text(display_frame, speed_str, (start_x, start_y), font, font_scale, osd_color, thickness)
            
            # 2. PID Values
            pid_str = f"P={current_kp:.2f} I={current_ki:.2f} D={current_kd:.2f}"
            draw_text(display_frame, pid_str, (start_x, start_y + line_height), font, font_scale, osd_color, thickness)
            
            # 3. Keybinds
            keys_str = "SPACE=TRACK WASD=MAN Q/E=SPEED Z=STAB"
            draw_text(display_frame, keys_str, (start_x, start_y + line_height * 2), font, font_scale, osd_color, thickness)
            
            # 4. Status Indicator (Vertically Centered)
            draw_text(display_frame, f"{status_text}", (start_x, h // 2), font, font_scale, osd_status_color, thickness)

            # Digital Stabilization Indicator
            dstb_text = "DSTAB ACT" if digital_stabilization_active else "DSTAB STBY"
            dstb_color = (0, 0, 255) if digital_stabilization_active else (255, 255, 255)
            draw_text(display_frame, dstb_text, (start_x, h // 2 + 25), font, font_scale, dstb_color, thickness)

            # 5. Graphical PTZ Gauges
            
            # Gauge Settings
            gauge_color = (255, 255, 255)
            gauge_radius = 60
            gauge_thickness = 2
            
            # Positions
            # Zoom: Bottom Center
            zoom_bar_w = 240
            zoom_bar_h = 20
            zoom_bar_x = (w - zoom_bar_w) // 2
            zoom_bar_y = h - 40
            
            # Pan/Tilt: Centered above Zoom
            # Place them side-by-side with a small gap
            gauge_gap = 40
            
            # Tilt on Left
            tilt_cx = (w // 2) - gauge_radius - (gauge_gap // 2)
            tilt_cy = zoom_bar_y - gauge_radius - 30
            
            # Pan on Right
            pan_cx = (w // 2) + gauge_radius + (gauge_gap // 2)
            pan_cy = tilt_cy
            
            # --- Pan Gauge (Full Circle) ---
            # Draw Ring
            draw_circle(display_frame, (pan_cx, pan_cy), gauge_radius, gauge_color, gauge_thickness)
            
            # Draw North Marker (Top)
            draw_line(display_frame, (pan_cx, pan_cy - gauge_radius), (pan_cx, pan_cy - gauge_radius + 5), gauge_color, 2)
            
            # Draw Indicator
            # Map Pan Degrees to Visual Angle
            # Cam 0 (North) -> Visual -90 (Top)
            # Cam +90 (East) -> Visual 0 (Right)
            # visual_angle = cam_angle - 90
            if 'pan_deg' in locals():
                p_rad = math.radians(pan_deg - 90)
                p_end_x = int(pan_cx + gauge_radius * math.cos(p_rad))
                p_end_y = int(pan_cy + gauge_radius * math.sin(p_rad))
                draw_line(display_frame, (pan_cx, pan_cy), (p_end_x, p_end_y), gauge_color, 2)
                
                # Text Value: Lower Right (Mirrored)
                draw_text(display_frame, f"{int(pan_deg)}", (pan_cx + gauge_radius + 5, pan_cy + gauge_radius), font, 1, gauge_color, 2)

            # --- Tilt Gauge (Arc) ---
            # Range: +90 (Up) to -30 (Down)
            # Visual Mapping:
            # Cam +90 -> Visual -90 (Top)
            # Cam 0 -> Visual 0 (Right)
            # Cam -30 -> Visual +30 (Bottom Right)
            # Arc Start: -90 (Top)
            # Arc End: +30
            
            # Draw Arc
            # ellipse(img, center, axes, angle, startAngle, endAngle, color, thickness)
            # Note: startAngle and endAngle are in degrees clockwise from the major axis.
            # If angle=0, major axis is horizontal (Right).
            # So startAngle=-90 (Top), endAngle=30 (Bottom Right).
            draw_ellipse(display_frame, (tilt_cx, tilt_cy), (gauge_radius, gauge_radius), 0, -90, 30, gauge_color, gauge_thickness)
            
            # Draw Horizon Marker (0 deg) -> Visual 0 (Right)
            h_mark_x = int(tilt_cx + gauge_radius)
            h_mark_y = tilt_cy
            draw_line(display_frame, (h_mark_x - 5, h_mark_y), (h_mark_x, h_mark_y), gauge_color, 2)
            
            # Draw Indicator
            if 'tilt_deg' in locals():
                # Clamp to limits for display safety
                disp_tilt = max(config.TILT_MIN_DEG, min(config.TILT_MAX_DEG, tilt_deg))
                
                # Visual Angle = -Camera Angle
                t_rad = math.radians(-disp_tilt)
                t_end_x = int(tilt_cx + gauge_radius * math.cos(t_rad))
                t_end_y = int(tilt_cy + gauge_radius * math.sin(t_rad))
                
                # Draw Line from Center
                draw_line(display_frame, (tilt_cx, tilt_cy), (t_end_x, t_end_y), gauge_color, 2)
                
                # Text Value: Lower Left (Mirrored)
                # Estimate width to align right
                t_str = f"{int(tilt_deg)}"
                (t_w, _), _ = cv2.getTextSize(t_str, font, 1, 1)
                draw_text(display_frame, t_str, (tilt_cx - gauge_radius - t_w - 5, tilt_cy + gauge_radius), font, 1, gauge_color, 2)

            # --- Zoom Gauge (Linear) ---
            # Draw Line
            draw_line(display_frame, (zoom_bar_x, zoom_bar_y), (zoom_bar_x + zoom_bar_w, zoom_bar_y), gauge_color, gauge_thickness)
            
            # Labels
            draw_text(display_frame, "W", (zoom_bar_x - 20, zoom_bar_y + 5), font, 1, gauge_color, 2)
            draw_text(display_frame, "N", (zoom_bar_x + zoom_bar_w + 10, zoom_bar_y + 5), font, 1, gauge_color, 2)
            
            # Indicator
            if z_pos is not None:
                # Map z_pos (0 to ZOOM_MAX_HEX) to (0 to zoom_bar_w)
                ratio = z_pos / config.ZOOM_MAX_HEX
                marker_x = int(zoom_bar_x + ratio * zoom_bar_w)
                
                # Draw Triangle/Tick
                # Triangle points up
                pt1 = (marker_x, zoom_bar_y)
                pt2 = (marker_x - 8, zoom_bar_y + 13)
                pt3 = (marker_x + 8, zoom_bar_y + 13)
                triangle_cnt = np.array([pt1, pt2, pt3])
                draw_poly_filled(display_frame, triangle_cnt, gauge_color)

            # Display
            # Force resize to 1920x1080 for consistent window size
            display_frame = cv2.resize(display_frame, (1920, 1080))
            cv2.imshow(window_name, display_frame)

            # Frame Rate Limiting
            # Calculate how long processing took
            process_time = time.time() - loop_start_time
            # Calculate remaining time to sleep to match target loop interval
            delay = config.LOOP_INTERVAL - process_time
            
            # cv2.waitKey expects integer milliseconds (at least 1)
            wait_ms = int(max(1, delay * 1000))
            
            # Key Handling
            key = cv2.waitKey(wait_ms) & 0xFF
            if key == 27: # ESC
                if tracking_active:
                    tracking_active = False
                    ptz.stop()
                else:
                    break
            elif key == 32: # SPACE
                if tracking_active:
                    # Disengage
                    tracking_active = False
                    kf = None # Reset Kalman Filter
                    ptz.stop()
                else:
                    # Engage Tracking on Center Reticle
                    # Use the defined reticle coordinates
                    half_size = config.RETICLE_SIZE // 2
                    rx1 = center_x - half_size
                    ry1 = center_y - half_size
                    w_box = config.RETICLE_SIZE
                    h_box = config.RETICLE_SIZE
                    
                    # Initialize Tracker
                    # Reverting to CSRT as requested
                    tracker = cv2.TrackerCSRT_create()
                    tracker.init(frame, (rx1, ry1, w_box, h_box))
                    tracking_active = True
                    kf = None # Reset Kalman Filter for new track
                    
                    # Reset PID state
                    prev_error_x = 0
                    prev_error_y = 0
                    error_sum_x = 0.0
                    error_sum_y = 0.0
                    prev_pan_speed = 0.0
                    prev_tilt_speed = 0.0
                    pan_accumulator = 0.0
                    tilt_accumulator = 0.0
            
            # Dynamic Speed Control Keys (Global)
            elif key == ord('q'):
                current_max_speed = max(1.0, current_max_speed - 0.25)
            elif key == ord('e'):
                current_max_speed = min(24, current_max_speed + 0.25) # Use a hard limit if defined, or just let it grow
            
            # Toggle Digital Stabilization
            elif key == ord('z'):
                digital_stabilization_active = not digital_stabilization_active
            
            # Dynamic PID Tuning Keys
            elif key == ord('1'): # P Up
                current_kp = round(current_kp + 0.01, 2)
            elif key == ord('2'): # P Down
                current_kp = max(0.0, round(current_kp - 0.01, 2))
            elif key == ord('3'): # I Up
                current_ki = round(current_ki + 0.01, 2)
            elif key == ord('4'): # I Down
                current_ki = max(0.0, round(current_ki - 0.01, 2))
            elif key == ord('5'): # D Up
                current_kd = round(current_kd + 0.01, 2)
            elif key == ord('6'): # D Down
                current_kd = max(0.0, round(current_kd - 0.01, 2))

            # Manual Control Keys (WASD) - Only if not tracking
            if not tracking_active:
                m_pan = 0
                m_tilt = 0
                moved = False
                
                if key == ord('w'):
                    m_tilt = config.MANUAL_SPEED # Reverted to original (Up)
                    moved = True
                elif key == ord('s'):
                    m_tilt = -config.MANUAL_SPEED # Reverted to original (Down)
                    moved = True
                    
                elif key == ord( 'a'):
                    m_pan = config.MANUAL_SPEED 
                    moved = True
                elif key == ord('d'):
                    m_pan = -config.MANUAL_SPEED
                    moved = True
                
                # Refined Manual Logic
                # We need to track if we are zooming or panning
                is_zooming = False
                
                if key == ord('r'): # Zoom In
                    ptz.zoom(config.ZOOM_SPEED)
                    is_zooming = True
                elif key == ord('f'): # Zoom Out
                    ptz.zoom(-config.ZOOM_SPEED)
                    is_zooming = True
                

                
                # Apply Inversion for Manual too? Usually yes.
                if config.PAN_INVERT: m_pan = -m_pan
                if config.TILT_INVERT: m_tilt = -m_tilt
                
                if moved:
                    ptz.pan_tilt(m_pan, m_tilt)
                    manual_mode_active = True
                    last_manual_time = time.time()
                elif is_zooming:
                    manual_mode_active = True
                    last_manual_time = time.time()
                else:
                    # If we were moving/zooming and now we are not, stop.
                    # Use a small timeout to avoid immediate stop on key release
                    if manual_mode_active and (time.time() - last_manual_time > MANUAL_TIMEOUT):
                        ptz.stop() # Stops both PT and Zoom
                        manual_mode_active = False

    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        # Cleanup
        print("Cleaning up...")
        if 'ptz' in locals():
            ptz.stop_polling()
            ptz.stop()
        if 'video' in locals():
            video.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
