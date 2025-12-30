import cv2
import numpy as np

class SkyWatchKalman:
    def __init__(self, initial_x, initial_y, process_noise=1e-5, measurement_noise=1e-1):
        """
        Initialize a Kalman Filter for tracking position (x, y) and velocity (vx, vy).
        State: [x, y, vx, vy]
        Measurement: [x, y]
        """
        self.kf = cv2.KalmanFilter(4, 2) # 4 dynamic params (x,y,vx,vy), 2 measurement params (x,y)
        
        # Measurement Matrix (H)
        # We measure x and y directly
        self.kf.measurementMatrix = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0]
        ], np.float32)
        
        # Transition Matrix (F) - Initial (dt will be updated)
        # [ 1  0  dt 0  ]
        # [ 0  1  0  dt ]
        # [ 0  0  1  0  ]
        # [ 0  0  0  1  ]
        self.kf.transitionMatrix = np.array([
            [1, 0, 1, 0],
            [0, 1, 0, 1],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ], np.float32)
        
        # Process Noise Covariance (Q)
        # How much we trust the model evolution. Lower = smoother, higher = more responsive to change.
        self.kf.processNoiseCov = np.eye(4, dtype=np.float32) * process_noise
        
        # Measurement Noise Covariance (R)
        # How much we trust the noisy measurements. Higher = more smoothing.
        self.kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * measurement_noise
        
        # Error Covariance (P) - Initial uncertainty
        self.kf.errorCovPost = np.eye(4, dtype=np.float32) * 1.0
        
        # Initial State
        self.kf.statePost = np.array([
            [np.float32(initial_x)], 
            [np.float32(initial_y)], 
            [0], 
            [0]
        ], dtype=np.float32)

    def predict(self, dt):
        """
        Predict the next state based on dt (time since last update).
        """
        # Update transition matrix with actual dt
        self.kf.transitionMatrix[0, 2] = dt
        self.kf.transitionMatrix[1, 3] = dt
        
        return self.kf.predict()

    def update(self, x, y):
        """
        Correct the state with a new measurement.
        """
        measurement = np.array([[np.float32(x)], [np.float32(y)]])
        self.kf.correct(measurement)
        return self.get_state()

    def get_state(self):
        """
        Returns (x, y, vx, vy)
        """
        return (
            self.kf.statePost[0, 0],
            self.kf.statePost[1, 0],
            self.kf.statePost[2, 0],
            self.kf.statePost[3, 0]
        )
