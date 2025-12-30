import cv2
print(f"OpenCV Version: {cv2.__version__}")
try:
    tracker = cv2.TrackerCSRT_create()
    print("cv2.TrackerCSRT_create() works")
except AttributeError:
    print("cv2.TrackerCSRT_create() failed")

try:
    tracker = cv2.TrackerCSRT.create()
    print("cv2.TrackerCSRT.create() works")
except AttributeError:
    print("cv2.TrackerCSRT.create() failed")
