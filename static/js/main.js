document.addEventListener('DOMContentLoaded', () => {
    // --- Elements ---
    const els = {
        date: document.getElementById('osd-date'),
        utc: document.getElementById('osd-utc'),
        local: document.getElementById('osd-local'),
        speed: document.getElementById('osd-speed'),
        pid: document.getElementById('osd-pid'),
        trackStatus: document.getElementById('osd-track-status'),
        stabStatus: document.getElementById('osd-stab-status'),
        az: document.getElementById('osd-az'),
        el: document.getElementById('osd-el'),
        zoom: document.getElementById('osd-zoom'),
        btnTrack: document.getElementById('btn-track'),
        btnStab: document.getElementById('btn-stab'),
        rangeSpeed: document.getElementById('range-speed'),
        valSpeed: document.getElementById('val-speed'),
        inP: document.getElementById('input-p'),
        inI: document.getElementById('input-i'),
        inD: document.getElementById('input-d'),
        inD: document.getElementById('input-d'),
        btnUpdatePid: document.getElementById('btn-update-pid'),
        btnRec: document.getElementById('btn-rec'),
        needlePan: document.getElementById('needle-pan'),
        needleTilt: document.getElementById('needle-tilt'),
        needleZoom: document.getElementById('needle-zoom')
    };

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
    };

    function updateUI(data) {
        // Time
        const now = new Date();
        els.date.innerText = now.toLocaleDateString();
        els.local.innerText = now.toLocaleTimeString('en-US', { hour12: false }) + " LCL";
        els.utc.innerText = now.toISOString().split('T')[1].split('.')[0] + " Z";

        // Status
        els.speed.innerText = `MAX SPD ${data.speed_limit.toFixed(2)} (SET)`;
        els.pid.innerText = `P=${data.kp.toFixed(2)} I=${data.ki.toFixed(2)} D=${data.kd.toFixed(2)}`;

        // Track Status
        els.trackStatus.innerText = data.status === "TRACKING" ? "TRK ACT" : "TRK STBY";
        els.trackStatus.style.color = data.track_active ? "#ff3333" : "#ffffff";

        els.stabStatus.innerText = data.stab_active ? "DSTAB ACT" : "DSTAB STBY";
        els.stabStatus.style.color = data.stab_active ? "#ff3333" : "#ffffff";

        // Buttons
        els.btnTrack.classList.toggle('active', data.track_active);
        els.btnTrack.innerText = data.track_active ? "STOP AUTO TRACK (SPACE)" : "START AUTO TRACK (SPACE)";

        els.btnStab.classList.toggle('active', data.stab_active);
        els.btnStab.innerText = data.stab_active ? "STOP DIGITAL STAB (Z)" : "START DIGITAL STAB (Z)";

        els.btnRec.classList.toggle('active', data.recording);
        els.btnRec.innerText = data.recording ? "STOP RECORDING (`)" : "START RECORDING (`)";

        // Gauges (Text)
        els.az.innerText = `AZ: ${data.pan !== undefined ? data.pan.toFixed(0).padStart(3, '0') : '---'}`;
        els.el.innerText = `EL: ${data.tilt !== undefined ? (data.tilt > 0 ? '+' : '') + data.tilt.toFixed(0) : '---'}`;
        els.zoom.innerText = `ZM: ${data.zoom ? data.zoom.toFixed(1) : '---'}X`;

        // SVG Gauges Logic
        if (data.pan !== undefined) {
            const panDeg = data.pan;
            els.needlePan.setAttribute('transform', `rotate(${panDeg}, 50, 50)`);
        }

        if (data.tilt !== undefined) {
            // Positive scale for pitch up
            const tiltDeg = data.tilt;
            els.needleTilt.setAttribute('transform', `rotate(${tiltDeg}, 50, 50)`);
        }

        if (data.zoom !== undefined) {
            const minZ = 1.0;
            const maxZ = 20.0;
            const pct = Math.max(0, Math.min(1, (data.zoom - minZ) / (maxZ - minZ)));
            const width = 290;
            const x = pct * width;
            els.needleZoom.setAttribute('transform', `translate(${x}, 0)`);
        }

        // Update Inputs only if not focused
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
            api({ action: 'toggle_record' });
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

        if (['w', 'a', 's', 'd', 'r', 'f'].includes(key)) {
            // If no movement keys left, loop will send 0
        }
    });

    function startManualLoop() {
        if (manualInterval) return;
        manualInterval = setInterval(() => {
            // Check keys
            let pan = 0, tilt = 0, zoom = 0;
            const spd = 50; // Manual Speed unit? Core expects something? Core uses config.MANUAL_SPEED
            // Actually core takes integer pan/tilt speeds. 
            // We should use a fixed speed here or read from config via API?
            // For now hardcode 'Manual Speed' as roughly 10-20?
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
                // Send one final zero command
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
    els.btnRec.onclick = () => api({ action: 'toggle_record' });

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

});
