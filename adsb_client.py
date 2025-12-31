import requests
import json
import time
import math
import config
import threading

class ADSBClient:
    def __init__(self):
        self.aircraft_data = []
        self.lock = threading.Lock()
        self.last_update = 0
        self.running = False
        self.thread = None

    def start(self):
        if self.running: return
        self.running = True
        self.thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.thread.start()
        print("ADS-B Client Started.")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        print("ADS-B Client Stopped.")

    def get_aircraft(self):
        with self.lock:
            # Return a copy to avoid threading issues
            return list(self.aircraft_data)

    def _poll_loop(self):
        while self.running:
            try:
                self._fetch_data()
            except Exception as e:
                print(f"Error fetching ADS-B data: {e}")
            
            time.sleep(1.0) # Poll at 1Hz

    def _fetch_data(self):
        try:
            response = requests.get(config.ADSB_URL, timeout=2.0)
            if response.status_code == 200:
                data = response.json()
                # Handle both dump1090 formats (root list or 'aircraft' key)
                ac_list = data.get('aircraft', []) if isinstance(data, dict) else data
                
                parsed_list = []
                current_time = time.time()

                for ac in ac_list:
                    # Filter invalid data
                    lat = ac.get('lat')
                    lon = ac.get('lon')
                    reg = ac.get('r') or ac.get('reg') or ac.get('registration') or '---'
                    try:
                        alt = int(ac.get('alt_baro') or ac.get('alt_geom') or 0)
                    except:
                        alt = 0

                    if lat is None or lon is None:
                        continue

                    # Calculate Distance and Bearing from Camera
                    dist_nm, bearing = self._calculate_position(lat, lon)

                    # Filter by range (e.g. 20nm) - Optional, but good for performance
                    if dist_nm > config.MAX_RANGE_NM * 1.5: 
                        continue

                    parsed_list.append({
                        'hex': ac.get('hex'),
                        'flight': ac.get('flight', '').strip(),
                        'reg': reg,
                        'type': ac.get('t') or ac.get('type') or '---',
                        'lat': lat,
                        'lon': lon,
                        'alt': alt,
                        'track': ac.get('track', 0),
                        'speed': ac.get('gs', 0),
                        'dist_nm': dist_nm,
                        'bearing': bearing,
                        'seen': ac.get('seen', 0),
                        'rssi': ac.get('rssi', -99.9)
                    })

                with self.lock:
                    self.aircraft_data = parsed_list
                    self.last_update = current_time

        except Exception as e:
             # print(f"ADS-B Fetch Error: {e}") 
             pass

    def _calculate_position(self, target_lat, target_lon):
        # Haversine Formula for distance
        R = 3440.065 # Earth radius in Nautical Miles

        lat1 = math.radians(config.CAMERA_LAT)
        lon1 = math.radians(config.CAMERA_LNG)
        lat2 = math.radians(target_lat)
        lon2 = math.radians(target_lon)

        dlon = lon2 - lon1
        dlat = lat2 - lat1

        a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
        c = 2 * math.asin(math.sqrt(a))
        dist_nm = R * c

        # Bearing Formula
        # y = sin(Δλ) * cos(φ2)
        # x = cos(φ1) * sin(φ2) - sin(φ1) * cos(φ2) * cos(Δλ)
        # θ = atan2(y, x)
        y = math.sin(dlon) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        
        bearing_rad = math.atan2(y, x)
        bearing_deg = (math.degrees(bearing_rad) + 360) % 360

        return dist_nm, bearing_deg
