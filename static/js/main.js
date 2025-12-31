document.addEventListener('DOMContentLoaded', () => {
    // --- Elements ---
    // --- Elements ---
    const els = {
        btnTrack: document.getElementById('btn-track'),
        btnStab: document.getElementById('btn-stab'),
        rangeSpeed: document.getElementById('range-speed'),
        valSpeed: document.getElementById('val-speed'),
        inP: document.getElementById('input-p'),
        inI: document.getElementById('input-i'),
        inD: document.getElementById('input-d'),
        btnUpdatePid: document.getElementById('btn-update-pid'),
        btnRec: document.getElementById('btn-rec'),
        video: document.getElementById('video-stream'),
        canvas: document.getElementById('osd-canvas')
    };

    const ctx = els.canvas.getContext('2d');

    // --- Recorder State ---
    let mediaRecorder = null;
    let recordedChunks = [];
    let isRecording = false;

    // --- State ---
    let keysPressed = {};
    let lastKeyTime = 0;
    let manualInterval = null;

    // --- API Calls ---
    async function api(data) {
        try {
            await fetch('/api/control', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
        } catch (e) {
            console.error(e);
        }
    }

    // --- Telemetry Loop (SSE) ---
    const evtSource = new EventSource("/api/telemetry");
    evtSource.onmessage = (e) => {
        const data = JSON.parse(e.data);
        updateUI(data);

        // If recording, renderLoop handles drawing.
        // If NOT recording, we must draw OSD here.
        if (!isRecording) {
            drawOSD(data);
        }
    };

    // Helper for OSD Text with Outline
    function drawOutlinedText(str, x, y) {
        ctx.strokeText(str, x, y);
        ctx.fillText(str, x, y);
    }

    // --- Canvas OSD Drawing ---
    function drawOSD(data, skipClear = false) {
        // Clear only if not compositing for recording
        if (!skipClear) {
            ctx.clearRect(0, 0, els.canvas.width, els.canvas.height);
        }

        // Setup Font & Outline Style
        ctx.font = '20px monospace';
        ctx.lineWidth = 3;
        ctx.strokeStyle = '#000000'; // Hard black outline
        // Remove global shadow
        ctx.shadowColor = 'transparent';
        ctx.shadowBlur = 0;
        ctx.shadowOffsetX = 0;
        ctx.shadowOffsetY = 0;

        const now = new Date();
        const dateStr = now.toLocaleDateString();
        const timeLcl = now.toLocaleTimeString('en-US', { hour12: false }) + ' LCL';
        const timeUtc = now.toISOString().split('T')[1].split('.')[0] + ' Z';

        // Top Left
        ctx.fillStyle = '#e0e0e0';
        ctx.textBaseline = 'top';
        ctx.textAlign = 'left';

        let y = 30; // Moved back up
        drawOutlinedText('AIRPLANE IAN SYSTEMS 401', 30, y); y += 30;
        drawOutlinedText(dateStr, 30, y); y += 30;
        drawOutlinedText(timeUtc, 30, y); y += 30;
        drawOutlinedText(timeLcl, 30, y);

        // Bottom Left
        y = els.canvas.height - 30;
        ctx.textBaseline = 'bottom';
        drawOutlinedText(`P=${data.kp.toFixed(2)} I=${data.ki.toFixed(2)} D=${data.kd.toFixed(2)}`, 30, y); y -= 30;
        drawOutlinedText(`MAX SPD ${data.speed_limit.toFixed(2)} (SET)`, 30, y); y -= 30;
        drawOutlinedText('EXP AUT', 30, y); y -= 30;
        drawOutlinedText('FOC MAN', 30, y); y -= 30;
        drawOutlinedText('HDEO', 30, y);

        // Left Center (Status)
        y = els.canvas.height / 2 - 15;
        ctx.textBaseline = 'middle';

        // Track Status
        const trkText = data.status === "TRACKING" ? "TRK ACT" : "TRK STBY";
        ctx.fillStyle = data.track_active ? '#ff3333' : '#ffffff';
        // Note: strokeStyle is black by default from above, but if we want red text, black outline works.
        // If we wanted red outline, we'd change strokeStyle. Keeping black outline for contrast.
        drawOutlinedText(trkText, 30, y);
        y += 30;

        // Stab Status
        const stabText = data.stab_active ? "DSTAB ACT" : "DSTAB STBY";
        ctx.fillStyle = data.stab_active ? '#ff3333' : '#e0e0e0';
        drawOutlinedText(stabText, 30, y);

        // --- Heading Tape (Top) ---
        drawHeadingTape(data);

        // --- North Arrow (Top Right) ---
        drawNorthArrow(data);

        // --- Gauges ---
        drawGauges(data);
    }

    function drawHeadingTape(data) {
        const panRaw = data.pan || 0;
        let camHeading = (panRaw + northOffset) % 360;
        if (camHeading < 0) camHeading += 360;

        const w = els.canvas.width;
        const cx = w / 2;
        const cy = 30;
        const fov = 60; // Tape always assumes nice wide FOV for readability or match zoom? 
        // Usually tape is fixed width per degree for readability. 
        // Let's say 10 pixels per degree? 
        const pxPerDeg = 8;

        ctx.save();
        ctx.beginPath();
        ctx.rect(cx - 200, 0, 400, 50); // Clip area
        ctx.clip(); // Optional, or just draw fading

        ctx.fillStyle = '#fff';
        ctx.strokeStyle = '#fff'; // Ticks are white lines, no outline needed usually, or add black shadow?
        // User asked for OSD text outline. Ticks are lines. Let's leave ticks as lines with maybe shadow?
        // But we just disabled global shadow.
        // Let's add simple shadow for ticks locally if needed, or black stroke borders for ticks?
        // Ticks: Just White line.

        // Reset styles for Ticks (Lines)
        ctx.lineWidth = 2;
        ctx.font = 'bold 16px monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';

        // Draw Ticks
        // Range: camHeading - 30 to camHeading + 30
        const startH = Math.floor(camHeading - 40);
        const endH = Math.ceil(camHeading + 40);

        for (let h = startH; h <= endH; h++) {
            // Norm H
            let hdg = h;
            // Normalized 0-360 for Display
            let displayH = hdg % 360;
            if (displayH < 0) displayH += 360;

            const offsetDeg = h - camHeading;
            const x = cx + offsetDeg * pxPerDeg;

            // Major Tick (10 deg)
            if (h % 10 === 0) {
                ctx.strokeStyle = '#fff'; // Ensure white ticks
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.moveTo(x, 10);
                ctx.lineTo(x, 25);
                ctx.stroke();

                // Text (Every 10 or 30?)
                let label = displayH.toString();
                if (displayH === 0) label = "N";
                if (displayH === 90) label = "E";
                if (displayH === 180) label = "S";
                if (displayH === 270) label = "W";

                // Draw label with outline
                ctx.fillStyle = '#fff';
                ctx.strokeStyle = '#000';
                ctx.lineWidth = 3;
                drawOutlinedText(label, x, 30);
            } else if (h % 5 === 0) {
                // Minor
                ctx.strokeStyle = '#fff'; // Ensure white ticks
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.moveTo(x, 15);
                ctx.lineTo(x, 25);
                ctx.stroke();
            }
        }
        ctx.restore();

        // Center Triangle (Static)
        ctx.fillStyle = '#fff';
        ctx.strokeStyle = '#000'; // Outline for triangle too?
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(cx, 35);
        ctx.lineTo(cx - 10, 50);
        ctx.lineTo(cx + 10, 50);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();

        // Value Box (Box Removed per request)
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 16px monospace';
        ctx.textBaseline = 'top';
        ctx.textAlign = 'center';

        ctx.lineWidth = 3;
        ctx.strokeStyle = '#000';
        drawOutlinedText(Math.round(camHeading).toString().padStart(3, '0'), cx, 55); // Moved to 55
    }

    function drawNorthArrow(data) {
        const panRaw = data.pan || 0;
        let camHeading = (panRaw + northOffset) % 360;
        if (camHeading < 0) camHeading += 360;

        // Arrow rotation = -Heading. 
        // 0 Hdg -> Arrow Up (0 rot).
        // 90 Hdg -> Arrow Left (-90 rot).
        const rot = -camHeading * (Math.PI / 180);

        const cx = els.canvas.width - 50;
        const cy = 50;

        ctx.save();
        ctx.translate(cx, cy);

        // --- Rotating Arrow ---
        ctx.save(); // Isolate rotation
        ctx.rotate(rot);

        // Arrow Shape (Pointing UP at 0 rot)
        // User requested White arrow with black shadow/outline.
        ctx.fillStyle = '#ffffff';
        ctx.strokeStyle = '#000000'; // Black outline
        ctx.lineWidth = 2; // Thicker outline for better visibility

        const totalLen = 60;
        const shaftW = 8;  // Reduced from 15
        const headW = 20;  // Reduced from 30
        const headLen = 25;

        ctx.beginPath();
        // Start bottom of shaft
        // y coords: Up is -y.
        // Shaft Bottom Left
        ctx.moveTo(-shaftW / 2, totalLen / 2);
        // Shaft Top Left (to Head base)
        ctx.lineTo(-shaftW / 2, -totalLen / 2 + headLen);
        // Head Left
        ctx.lineTo(-headW / 2, -totalLen / 2 + headLen);
        // Head Tip
        ctx.lineTo(0, -totalLen / 2);
        // Head Right
        ctx.lineTo(headW / 2, -totalLen / 2 + headLen);
        // Shaft Top Right
        ctx.lineTo(shaftW / 2, -totalLen / 2 + headLen);
        // Shaft Bottom Right
        ctx.lineTo(shaftW / 2, totalLen / 2);

        ctx.closePath();

        ctx.shadowColor = 'transparent'; // Ensure no shadow
        ctx.fill();
        ctx.stroke();

        ctx.restore(); // End rotation

        // --- Static N ---
        // N (White text with black outline/shadow)
        ctx.font = 'bold 18px monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        // Stroke first (the "Shadow/Outline" separator)
        ctx.strokeStyle = '#000000';
        ctx.lineWidth = 4; // Thick stroke to separate from white arrow
        ctx.strokeText("N", 0, 1);

        // Fill second (White)
        ctx.fillStyle = '#ffffff';
        ctx.fillText("N", 0, 1);

        ctx.restore(); // End translation
    }

    function drawGauges(data) {
        // Bottom Center
        const cx = els.canvas.width / 2;
        const cy = els.canvas.height - 60; // 30 (margin) + 30 (half gauge height assumed)

        // Settings
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 3;
        ctx.shadowOffsetX = 1;
        ctx.shadowOffsetY = 1;

        // 1. Tilt Gauge (Left of center)
        const tiltCx = cx - 70;
        const tiltCy = els.canvas.height - 80;
        const r = 35;

        // Arc
        // Start roughly 200 deg to 160 deg? Previous SVG logic was specific.
        // Let's draw arc on left side.
        ctx.beginPath();
        // 135 deg to 225 deg (Left side arc)
        // 135 deg = 2.356 rad, 225 deg = 3.926 rad
        ctx.arc(tiltCx, tiltCy, r, 2.356, 3.926);
        ctx.stroke();

        // Center Tick (Left/180)
        ctx.beginPath();
        ctx.moveTo(tiltCx - r, tiltCy);
        ctx.lineTo(tiltCx - r + 10, tiltCy);
        ctx.stroke();

        // Needle
        // Map tilt -60..+60 to angle?
        // Let's assume tilt is passed as degrees.
        // 0 deg = Left (180). +60 = Up-ish? -60 = Down-ish.
        // SVG Coord is Y-down.
        // 0 deg tilt = 180 deg angle.
        // +tilt (Up) -> 220 deg? (Move CCW on screen).
        // -tilt (Down) -> 140 deg?
        let tiltDeg = data.tilt || 0;
        // Clamp visually
        tiltDeg = Math.max(-60, Math.min(60, tiltDeg));
        // 180 is West. Up is 270 (-90).
        // If we want +tilt to go "Up" (towards 270), we subtract. 
        // User requested reversal: +tilt should go "Down" (towards 90) or vice versa.
        // Reversing the sign.
        const tiltAngleRad = (180 + tiltDeg) * (Math.PI / 180); // In HTML5 Canvas, 0 is East, 90 South. 

        const tx = tiltCx + r * Math.cos(tiltAngleRad);
        const ty = tiltCy + r * Math.sin(tiltAngleRad);
        ctx.beginPath();
        ctx.moveTo(tiltCx, tiltCy);
        ctx.lineTo(tx, ty);
        ctx.stroke();

        // 2. Pan Gauge (Center? No, Left group in SVG was Tilt/Pan)
        // Let's put Pan to the right of Tilt.
        const panCx = cx + 70;
        const panCy = tiltCy;

        // Full Circle
        ctx.beginPath();
        ctx.arc(panCx, panCy, r, 0, 2 * Math.PI);
        ctx.stroke();

        // North Tick
        ctx.beginPath();
        ctx.moveTo(panCx, panCy - r);
        ctx.lineTo(panCx, panCy - r + 10);
        ctx.stroke();

        // Needle
        let panDeg = data.pan || 0;
        // 0 is North? usually. 
        // Standard angle: 0 East. -90 North. 
        // If pan is 0->North. 90->East.
        // Canvas angle = pan - 90.
        const panRad = (panDeg - 90) * (Math.PI / 180);
        const px = panCx + r * Math.cos(panRad);
        const py = panCy + r * Math.sin(panRad);
        ctx.beginPath();
        ctx.moveTo(panCx, panCy);
        ctx.lineTo(px, py);
        ctx.stroke();

        // 3. Zoom Gauge (Bar below)
        const zoomW = 290;
        const zoomY = els.canvas.height - 30;
        const zoomX = cx - zoomW / 2;

        // Line
        ctx.beginPath();
        ctx.moveTo(zoomX, zoomY);
        ctx.lineTo(zoomX + zoomW, zoomY);
        ctx.stroke();

        // Labels
        ctx.font = 'bold 20px monospace';
        ctx.textAlign = 'right';
        ctx.fillText('W', zoomX - 10, zoomY + 7); // +7 for vertical align approx
        ctx.textAlign = 'left';
        ctx.fillText('N', zoomX + zoomW + 10, zoomY + 7);

        // Marker
        let zoom = data.zoom || 1.0;
        // 1.0 to 20.0 (or max)
        const minZ = 1.0;
        const maxZ = 20.0; // from config
        const pct = Math.max(0, Math.min(1, (zoom - minZ) / (maxZ - minZ)));
        const markerX = zoomX + pct * zoomW;

        ctx.fillStyle = '#fff';
        ctx.beginPath();
        // Pointing DOWN to the line from ABOVE
        // Base at zoomY - 10, Tip at zoomY
        ctx.moveTo(markerX - 5, zoomY - 10);
        ctx.lineTo(markerX + 5, zoomY - 10);
        ctx.lineTo(markerX, zoomY);
        ctx.fill();
    }

    // --- Recorder Logic ---
    function startRecording() {
        if (isRecording) return;

        console.log("Starting Recording...");
        const stream = els.canvas.captureStream(30); // 30 FPS

        // Default to webm/vp9 if supported, else standard webm
        let options = { mimeType: 'video/webm; codecs=vp9' };
        if (!MediaRecorder.isTypeSupported(options.mimeType)) {
            options = { mimeType: 'video/webm' };
        }

        try {
            mediaRecorder = new MediaRecorder(stream, options);
        } catch (e) {
            console.warn("VP9 not supported, trying default.");
            mediaRecorder = new MediaRecorder(stream);
        }

        recordedChunks = [];
        mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) recordedChunks.push(e.data);
        };

        mediaRecorder.onstop = () => {
            const blob = new Blob(recordedChunks, { type: 'video/webm' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            const filename = `skywatch_rec_${new Date().toISOString().replace(/[:.]/g, '-')}.webm`;
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            setTimeout(() => {
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
            }, 100);
            console.log("Recording Saved");
        };

        mediaRecorder.start();
        isRecording = true;

        // Start Render Loop for Canvas (Video + OSD)
        renderLoop();

        // Update UI
        els.btnRec.innerText = "RECORDING DISABLE (`)"
        els.btnRec.classList.add('active');
    }

    function stopRecording() {
        if (!isRecording) return;
        isRecording = false; // Stops the render loop
        mediaRecorder.stop();

        // Clear canvas or return to transparent OSD only?
        // If we stop drawing video, the canvas becomes transparent (if we clear it), revealing the <img> behind.
        // Yes, `drawOSD` clears rect.
        // So we revert to just drawing OSD on transparent canvas, allowing <img> to show.

        els.btnRec.innerText = "RECORDING ENABLE (`)"
        els.btnRec.classList.remove('active');
    }

    // Render loop for Recording (Composites Video + OSD)
    function renderLoop() {
        if (!isRecording) return;

        // 1. Draw Video Frame
        // Note: els.video is an HTMLImageElement with MJPEG source. 
        // Use 'img' source for drawImage.
        try {
            ctx.drawImage(els.video, 0, 0, els.canvas.width, els.canvas.height);
        } catch (e) {
            // Video might not be ready
        }

        // 2. Draw OSD
        if (latestOSDData) {
            // Force skipClear=true to overlay on top of video
            drawOSD(latestOSDData, true);
        }

        requestAnimationFrame(renderLoop);
    }

    let latestOSDData = null; // Cache

    function updateUI(data) {
        latestOSDData = data;

        // Buttons Update
        els.btnTrack.classList.toggle('active', data.track_active);
        els.btnTrack.innerText = data.track_active ? "AUTO TRACK DISABLE (SPACE)" : "AUTO TRACK ENABLE (SPACE)";

        els.btnStab.classList.toggle('active', data.stab_active);
        els.btnStab.innerText = data.stab_active ? "DIGITAL STAB DISABLE (Z)" : "DIGITAL STAB ENABLE (Z)";

        // Inputs
        if (document.activeElement !== els.inP) els.inP.value = data.kp;
        if (document.activeElement !== els.inI) els.inI.value = data.ki;
        if (document.activeElement !== els.inD) els.inD.value = data.kd;
        if (document.activeElement !== els.rangeSpeed) {
            els.rangeSpeed.value = data.speed_limit;
            els.valSpeed.innerText = data.speed_limit;
        }
    }

    // --- Inputs ---

    // Key Handling
    window.addEventListener('keydown', (e) => {
        if (e.target.tagName === 'INPUT') return; // Ignore if typing

        const key = e.key.toLowerCase();

        if (keysPressed[key]) return; // Repeat check
        keysPressed[key] = true;

        if (key === ' ') {
            e.preventDefault();
            api({ action: 'toggle_track' });
        } else if (key === 'z') {
            api({ action: 'toggle_stab' });
        } else if (key === '`') {
            if (isRecording) stopRecording();
            else startRecording();
        } else if (key === 'q') {
            adjustSpeed(-0.5);
        } else if (key === 'e') {
            adjustSpeed(0.5);
        } else if (['w', 'a', 's', 'd', 'r', 'f'].includes(key)) {
            startManualLoop();
        }
    });

    window.addEventListener('keyup', (e) => {
        const key = e.key.toLowerCase();
        delete keysPressed[key];
    });

    function startManualLoop() {
        if (manualInterval) return;
        manualInterval = setInterval(() => {
            // Check keys
            let pan = 0, tilt = 0, zoom = 0;
            const manual_speed = 15;
            const zoom_speed = 3;

            if (keysPressed['w']) tilt = manual_speed;
            if (keysPressed['s']) tilt = -manual_speed;
            if (keysPressed['a']) pan = manual_speed;
            if (keysPressed['d']) pan = -manual_speed;

            if (keysPressed['r']) zoom = zoom_speed;
            if (keysPressed['f']) zoom = -zoom_speed;

            if (pan === 0 && tilt === 0 && zoom === 0) {
                // Stop loop if keys released
                clearInterval(manualInterval);
                manualInterval = null;
            }

            // Send
            api({ action: 'move', pan, tilt, zoom });

        }, 100); // 10Hz
    }

    function adjustSpeed(delta) {
        let val = parseFloat(els.rangeSpeed.value) + delta;
        val = Math.max(0.5, Math.min(24, val));
        api({ action: 'set_speed', speed: val });
    }

    // UI Listeners
    els.btnTrack.onclick = () => api({ action: 'toggle_track' });
    els.btnStab.onclick = () => api({ action: 'toggle_stab' });
    els.btnRec.onclick = () => {
        if (isRecording) stopRecording();
        else startRecording();
    };

    els.rangeSpeed.oninput = (e) => els.valSpeed.innerText = e.target.value;
    els.rangeSpeed.onchange = (e) => api({ action: 'set_speed', speed: parseFloat(e.target.value) });

    els.btnUpdatePid.onclick = () => {
        api({
            action: 'set_pid',
            p: parseFloat(els.inP.value),
            i: parseFloat(els.inI.value),
            d: parseFloat(els.inD.value)
        });
    };

    // Touch/Click D-Pad
    document.querySelectorAll('.d-btn, .z-btn').forEach(btn => {
        const key = btn.dataset.key;
        btn.addEventListener('mousedown', () => {
            keysPressed[key] = true;
            startManualLoop();
        });
        btn.addEventListener('mouseup', () => {
            delete keysPressed[key];
        });
        btn.addEventListener('mouseleave', () => {
            delete keysPressed[key];
        });
    });




    // --- Radar Controller ---
    const radarCanvas = document.getElementById('radar-canvas');
    const radarCtx = radarCanvas.getContext('2d');
    const aircraftInfoDiv = document.getElementById('aircraft-info');
    const inputOffset = document.getElementById('input-offset');

    const CONFIG = {
        CAMERA_LAT: 37.818728,
        CAMERA_LNG: -122.268427,
        MAX_RANGE_NM: 10,
        FOV_DEG: 5.0, // Default approx, acts as beam width for "locked" check if zoom unknown
        // Note: Real FOV depends on Zoom. We have data.zoom.
        // Approx: Wide=60deg, Tele=2deg? 
        // Let's assume ZOOM 1.0 = 60 deg, ZOOM 20.0 = 3 deg.
        MIN_FOV: 3.0,
        MAX_FOV: 60.0,
        MAX_ZOOM: 20.0
    };

    let aircraftData = [];
    let northOffset = parseInt(localStorage.getItem('skywatch_north_offset') || '0');
    inputOffset.value = northOffset;

    inputOffset.addEventListener('change', (e) => {
        northOffset = parseInt(e.target.value);
        localStorage.setItem('skywatch_north_offset', northOffset);
    });

    // Poll Aircraft Data
    setInterval(async () => {
        try {
            const res = await fetch('/api/aircraft');
            if (res.ok) {
                aircraftData = await res.json();
                drawRadar();
                updateInfoBox();
            }
        } catch (e) {
            console.warn("Aircraft Poll Error", e);
        }
    }, 1000);

    // Radar Draw Loop
    // Triggered by aircraft poll and telemetry updates

    function drawRadar() {
        const w = radarCanvas.width;
        const h = radarCanvas.height;
        const cx = w / 2;
        const cy = h / 2;
        const pxPerNm = (w / 2) / (CONFIG.MAX_RANGE_NM * 1.1); // Leave some margin

        // Clear
        radarCtx.fillStyle = '#000';
        radarCtx.fillRect(0, 0, w, h);

        // Grid (Rings)
        radarCtx.strokeStyle = '#333';
        radarCtx.lineWidth = 2; // Thicker grid

        [2, 4, 6, 8, 10].forEach(nm => {
            radarCtx.beginPath();
            radarCtx.arc(cx, cy, nm * pxPerNm, 0, 2 * Math.PI);
            radarCtx.stroke();
            // Label
            radarCtx.fillStyle = '#666'; // Brighter text
            radarCtx.font = 'bold 12px monospace'; // Larger text
            radarCtx.fillText(`${nm}NM`, cx + 5, cy - (nm * pxPerNm) + 12);
        });

        // Crosshairs
        radarCtx.beginPath();
        radarCtx.moveTo(0, cy);
        radarCtx.lineTo(w, cy);
        radarCtx.moveTo(cx, 0);
        radarCtx.lineTo(cx, h);
        radarCtx.stroke();

        // --- Camera Wedge ---
        // Need current Pan/Heading
        if (latestOSDData) {
            const panRaw = latestOSDData.pan || 0;
            // North Up Map.
            // Camera Heading = (panRaw + northOffset) % 360
            let camHeading = (panRaw + northOffset) % 360;
            if (camHeading < 0) camHeading += 360;

            // Calculate FOV
            const zoom = latestOSDData.zoom || 1.0;
            // Linear interp for FOV? 
            // 1.0 -> 60, 20.0 -> 3
            // fov = 60 - ((zoom - 1) / (19)) * (57)
            const fov = Math.max(CONFIG.MIN_FOV, CONFIG.MAX_FOV - ((zoom - 1.0) / (CONFIG.MAX_ZOOM - 1.0)) * (CONFIG.MAX_FOV - CONFIG.MIN_FOV));

            const halfFovRad = (fov / 2) * (Math.PI / 180);

            // Canvas Angle: 0 is Right (East), 90 Down (South), -90 Up (North).
            // We want North Up.
            // So North (0 deg heading) should correspond to -90 deg canvas angle.
            // CanvasAngle = Heading - 90.
            const wedgeCenterRad = (camHeading - 90) * (Math.PI / 180);

            radarCtx.fillStyle = 'rgba(255, 255, 255, 0.25)'; // More visible wedge
            radarCtx.beginPath();
            radarCtx.moveTo(cx, cy);
            radarCtx.arc(cx, cy, w, wedgeCenterRad - halfFovRad, wedgeCenterRad + halfFovRad);
            radarCtx.moveTo(cx, cy);
            radarCtx.fill();

            // Camera Line
            radarCtx.lineWidth = 3;
            radarCtx.strokeStyle = '#33ff33'; // Bright Green Heading Line
            radarCtx.beginPath();
            radarCtx.moveTo(cx, cy);
            radarCtx.lineTo(cx + w * Math.cos(wedgeCenterRad), cy + w * Math.sin(wedgeCenterRad));
            radarCtx.stroke();
            radarCtx.lineWidth = 2; // Reset
        }

        // --- Aircraft ---
        aircraftData.forEach(ac => {
            // Plot logic
            // ac.dist_nm, ac.bearing (True bearing from cam)
            // North Up plot: 
            // Bearing 0 -> Up (canvas -90)
            // Angle = Bearing - 90

            const r = ac.dist_nm * pxPerNm;
            if (r > w / 2) return; // Out of bounds

            const angleRad = (ac.bearing - 90) * (Math.PI / 180);
            const x = cx + r * Math.cos(angleRad);
            const y = cy + r * Math.sin(angleRad);

            // Draw Blip
            // Check if "In View" (Target)
            const isTarget = checkInView(ac);

            radarCtx.fillStyle = isTarget ? '#ffff00' : '#00ffff';

            // Diamond shape for target, Dot for others
            if (isTarget) {
                const s = 10; // Size
                radarCtx.beginPath();
                radarCtx.moveTo(x, y - s);
                radarCtx.lineTo(x + s, y);
                radarCtx.lineTo(x, y + s);
                radarCtx.lineTo(x - s, y);
                radarCtx.fill();
            } else {
                radarCtx.beginPath();
                radarCtx.arc(x, y, 5, 0, 2 * Math.PI); // Larger dot
                radarCtx.fill();
            }

            // Label (Flight or Alt)
            radarCtx.fillStyle = '#fff';
            radarCtx.font = 'bold 14px monospace'; // Larger label
            const label = ac.flight || (ac.alt + "ft");
            radarCtx.fillText(label, x + 12, y + 4);
        });
    }

    function checkInView(ac) {
        if (!latestOSDData) return false;

        const panRaw = latestOSDData.pan || 0;
        let camHeading = (panRaw + northOffset) % 360;
        if (camHeading < 0) camHeading += 360;

        // Simplified: Only use Pan/Heading. Ignored Zoom/Tilt.
        const SELECTION_FOV = 20; // 20 degrees fixed selection window

        // Angle diff
        let diff = Math.abs(ac.bearing - camHeading);
        if (diff > 180) diff = 360 - diff;

        return diff < (SELECTION_FOV / 2);
    }

    function updateInfoBox() {
        // Find best target (closest to center of view, valid range)
        // For now, just pick the first one that returns true for checkInView
        // Or closest to center line.

        let bestTarget = null;
        let minDiff = 999;

        if (latestOSDData) {
            const panRaw = latestOSDData.pan || 0;
            let camHeading = (panRaw + northOffset) % 360;
            if (camHeading < 0) camHeading += 360;

            aircraftData.forEach(ac => {
                if (checkInView(ac)) {
                    let diff = Math.abs(ac.bearing - camHeading);
                    if (diff > 180) diff = 360 - diff;

                    if (diff < minDiff) {
                        minDiff = diff;
                        bestTarget = ac;
                    }
                }
            });
        }

        // Default Values
        let flight = '---';
        let reg = '---';
        let type = '---'; // Add ICAO Type
        let dist = '---';
        let alt = '---';
        let speed = '---';
        let bearing = '---';

        if (bestTarget) {
            flight = bestTarget.flight || 'N/A';
            reg = bestTarget.reg || '---';
            type = bestTarget.type || '---';
            dist = bestTarget.dist_nm.toFixed(1);
            alt = bestTarget.alt;
            speed = bestTarget.speed.toFixed(0);
            bearing = bestTarget.bearing.toFixed(0);
        }

        aircraftInfoDiv.innerHTML = `
            <div class="info-header">AIRCRAFT INFO</div>
            <div class="info-dashboard">
                <div class="dash-item">
                    <span class="dash-label">FLIGHT</span>
                    <span class="dash-value highlight">${flight}</span>
                </div>
                 <div class="dash-item">
                    <span class="dash-label">REG</span>
                    <span class="dash-value">${reg}</span>
                </div>
                 <div class="dash-item">
                    <span class="dash-label">ICAO</span>
                    <span class="dash-value">${type}</span>
                </div>
                <div class="dash-item">
                    <span class="dash-label">RANGE</span>
                    <span class="dash-value">${dist} <span style="font-size:0.5em">NM</span></span>
                </div>
                <div class="dash-item">
                    <span class="dash-label">ALTITUDE</span>
                    <span class="dash-value">${alt} <span style="font-size:0.5em">FT</span></span>
                </div>
                <div class="dash-item">
                    <span class="dash-label">SPEED</span>
                    <span class="dash-value">${speed} <span style="font-size:0.5em">KTS</span></span>
                </div>
                <div class="dash-item">
                    <span class="dash-label">BEARING</span>
                    <span class="dash-value">${bearing}°</span>
                </div>
            </div>
        `;
    }


    // Radar Render Loop (Animation Frame)
    function radarLoop() {
        drawRadar();
        requestAnimationFrame(radarLoop);
    }
    radarLoop();

});
