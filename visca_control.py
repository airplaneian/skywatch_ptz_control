import socket
import binascii
import threading
import time

class CameraControl:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP
        self.sock.settimeout(0.5) # Timeout for receiving
        self.address = (self.ip, self.port)
        self.sequence_number = 1
        self.sequence_number = 1
        self.lock = threading.Lock() # Thread safety for socket access
        
        # Polling State
        self.polling_active = False
        self.poll_thread = None
        self.cached_zoom = None
        self.cached_pan = None
        self.cached_tilt = None
        
        print(f"Initialized VISCA UDP Controller at {self.ip}:{self.port}")

    def _send_packet(self, payload):
        with self.lock:
            try:
                self.sock.sendto(payload, self.address)
                self.sequence_number += 1
            except Exception as e:
                print(f"Error sending UDP packet: {e}")

    def _receive_packet(self):
        # Socket recv is blocking with timeout, so we rely on the
        # polling thread to handle continuous reads.
        try:
            data, addr = self.sock.recvfrom(1024)
            return data
        except socket.timeout:
            return None
        except Exception as e:
            print(f"Error receiving UDP packet: {e}")
            return None

    def start_polling(self, interval=0.2):
        if self.polling_active:
            return
        self.polling_active = True
        # Set a short timeout for the listener loop to ensure we can check for exit/sending queries
        self.sock.settimeout(0.01) 
        self.poll_thread = threading.Thread(target=self._listen_loop, args=(interval,), daemon=True)
        self.poll_thread.start()
        print("Started VISCA Listener/Poller Thread.")

    def stop_polling(self):
        self.polling_active = False
        if self.poll_thread:
            self.poll_thread.join(timeout=1.0)

    def _listen_loop(self, interval):
        last_query_time = 0
        while self.polling_active:
            # 1. Periodic Query Injection
            now = time.time()
            if now - last_query_time > interval:
                self._send_zoom_inq()
                self._send_pan_tilt_inq()
                last_query_time = now
            
            # 2. Continuous Read (Drain Buffer)
            try:
                data, addr = self.sock.recvfrom(1024)
                if data:
                    self._process_packet(data)
            except socket.timeout:
                pass # Normal, just loop back
            except Exception as e:
                print(f"Error receiving UDP packet: {e}")
                time.sleep(0.1) # Avoid tight loop on error

    def _process_packet(self, data):
        """
        Parses incoming VISCA packets.
        Standard VISCA response format: y0 50 ... FF
        where y = Source Address + 8 (Camera 1 -> 0x90)
        """
        if len(data) < 3: return
        
        # Check for Inquiry Completion (0x50 in byte 1)
        if data[1] == 0x50:
            # Differentiate based on packet length
            # Zoom Inquiry Response is 7 bytes
            # Pan/Tilt Inquiry Response is 11 bytes
            
            if len(data) == 7:
                # Assume Zoom
                p = data[2] & 0x0F
                q = data[3] & 0x0F
                r = data[4] & 0x0F
                s = data[5] & 0x0F
                self.cached_zoom = (p << 12) | (q << 8) | (r << 4) | s
                
            elif len(data) == 11:
                # Assume Pan/Tilt
                # y0 50 0w 0w 0w 0w 0z 0z 0z 0z FF
                pw1 = data[2] & 0x0F
                pw2 = data[3] & 0x0F
                pw3 = data[4] & 0x0F
                pw4 = data[5] & 0x0F
                self.cached_pan = (pw1 << 12) | (pw2 << 8) | (pw3 << 4) | pw4
                
                tw1 = data[6] & 0x0F
                tw2 = data[7] & 0x0F
                tw3 = data[8] & 0x0F
                tw4 = data[9] & 0x0F
                self.cached_tilt = (tw1 << 12) | (tw2 << 8) | (tw3 << 4) | tw4

    def _send_zoom_inq(self):
        # CAM_ZoomPosInq: 81 09 04 47 FF
        cmd = bytearray([0x81, 0x09, 0x04, 0x47, 0xFF])
        self._send_packet(cmd)

    def _send_pan_tilt_inq(self):
        # Pan-tiltPosInq: 81 09 06 12 FF
        cmd = bytearray([0x81, 0x09, 0x06, 0x12, 0xFF])
        self._send_packet(cmd)

    def get_cached_pos(self):
        """Returns the most recently received position data."""
        return self.cached_zoom, self.cached_pan, self.cached_tilt
    def get_zoom_pos(self):
        return self.cached_zoom

    def get_pan_tilt_pos(self):
        return self.cached_pan, self.cached_tilt

    def pan_tilt(self, pan_speed, tilt_speed):
        """
        pan_speed: -24 to 24
        tilt_speed: -20 to 20
        """
        pan_dir = 3
        tilt_dir = 3
        
        p_speed = int(abs(pan_speed))
        t_speed = int(abs(tilt_speed))
        
        if pan_speed > 0: pan_dir = 2 # Right
        elif pan_speed < 0: pan_dir = 1 # Left
        
        if tilt_speed > 0: tilt_dir = 1 # Up
        elif tilt_speed < 0: tilt_dir = 2 # Down
        
        # Construct command
        # 81 01 06 01 VV WW XX YY FF
        cmd = bytearray([0x81, 0x01, 0x06, 0x01, p_speed, t_speed, pan_dir, tilt_dir, 0xFF])
        self._send_packet(cmd)

    def stop(self):
        # Stop command: 81 01 06 01 00 00 03 03 FF (Pan/Tilt Stop)
        cmd_pt = bytearray([0x81, 0x01, 0x06, 0x01, 0x00, 0x00, 0x03, 0x03, 0xFF])
        self._send_packet(cmd_pt)
        
        # Zoom Stop: 81 01 04 07 00 FF
        cmd_z = bytearray([0x81, 0x01, 0x04, 0x07, 0x00, 0xFF])
        self._send_packet(cmd_z)

    def home(self):
        # Home: 81 01 06 04 FF
        cmd = bytearray([0x81, 0x01, 0x06, 0x04, 0xFF])
        self._send_packet(cmd)
        
    def zoom(self, speed):
        s = int(abs(speed))
        if s > 7: s = 7
        
        if speed > 0: # Tele
            cmd = bytearray([0x81, 0x01, 0x04, 0x07, 0x20 | s, 0xFF])
        elif speed < 0: # Wide
            cmd = bytearray([0x81, 0x01, 0x04, 0x07, 0x30 | s, 0xFF])
        else:
            cmd = bytearray([0x81, 0x01, 0x04, 0x07, 0x00, 0xFF])
            
        self._send_packet(cmd)
