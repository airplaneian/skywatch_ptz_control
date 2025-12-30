from flask import Flask, render_template, Response, request, jsonify, stream_with_context
import time
import json
import threading
from skywatch_core import SkyWatchCore
import cv2

app = Flask(__name__)

# Global Core Instance
core = SkyWatchCore()

def generate_mjpeg():
    """Generator for MJPEG stream."""
    while True:
        frame = core.get_frame()
        if frame is None:
            time.sleep(0.01)
            continue
            
        # Encode
        (flag, encodedImage) = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not flag:
            continue
            
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + bytearray(encodedImage) + b'\r\n')
        
        # Limit frame rate of stream slightly to save bandwidth? 
        # Or run as fast as possible. 
        time.sleep(0.016) # ~60fps cap

def generate_telemetry():
    """Generator for SSE Telemetry."""
    while True:
        data = core.get_telemetry_data()
        data['timestamp'] = time.time()
        yield f"data: {json.dumps(data)}\n\n"
        time.sleep(0.05) # ~20Hz updates

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(stream_with_context(generate_mjpeg()),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/telemetry')
def telemetry_feed():
    return Response(stream_with_context(generate_telemetry()),
                    mimetype='text/event-stream')

@app.route('/api/control', methods=['POST'])
def control():
    cmd = request.json
    action = cmd.get('action')
    
    if action == 'move':
        pan = float(cmd.get('pan', 0))
        tilt = float(cmd.get('tilt', 0))
        zoom = float(cmd.get('zoom', 0))
        core.set_manual_command(pan, tilt, zoom)
        
    elif action == 'toggle_track':
        core.toggle_tracking()
        
    elif action == 'toggle_stab':
        core.toggle_stabilization()

    elif action == 'toggle_record':
        core.toggle_recording()
        
    elif action == 'set_pid':
        p = float(cmd.get('p'))
        i = float(cmd.get('i'))
        d = float(cmd.get('d'))
        core.set_pid(p, i, d)
        
    elif action == 'set_speed':
        s = float(cmd.get('speed'))
        core.set_max_speed(s)
        
    return jsonify({'status': 'ok'})

def start_server():
    # Start Core
    core.start()
    
    # Start Flask
    # Note: debug=False, threaded=True is default
    app.run(host='0.0.0.0', port=5001, debug=False, use_reloader=False)

if __name__ == '__main__':
    try:
        start_server()
    except KeyboardInterrupt:
        pass
    finally:
        core.stop()
