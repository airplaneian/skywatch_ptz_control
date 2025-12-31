import cv2
import threading
import time


class ThreadedVideoCapture:
    def __init__(self, src=0, name="ThreadedVideoCapture"):
        self.src = src
        self.cap = cv2.VideoCapture(self.src)
        # Optimize buffer size for low latency
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.grabbed, self.frame = self.cap.read()
        self.started = False
        self.read_lock = threading.Lock()
        self.name = name

    def start(self):
        if self.started:
            print(f"[{self.name}] Already started.")
            return self
        self.started = True
        self.thread = threading.Thread(target=self.update, args=(), daemon=True)
        self.thread.start()
        print(f"[{self.name}] Thread started.")
        return self

    def update(self):
        while self.started:
            grabbed, frame = self.cap.read()
            with self.read_lock:
                self.grabbed = grabbed
                self.frame = frame
            
            # Prevents CPU spin on read failure
            if not grabbed:
                time.sleep(0.1)

    def read(self):
        with self.read_lock:
            if not self.grabbed:
                return None
            return self.frame.copy()

    def stop(self):
        self.started = False
        if self.thread.is_alive():
            self.thread.join()
        self.cap.release()
        print(f"[{self.name}] Thread stopped and camera released.")

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()
