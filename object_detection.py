import cv2
import easyocr
import numpy as np
from ultralytics import YOLO
from pyzbar.pyzbar import decode

class ObjectDetector:
    def __init__(self):
        self.reader = easyocr.Reader(['en'])
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml') # OpenCV Face Detector (Haar cascade)
        self.yolo_model = YOLO("yolov8n.pt")

    def detect_cues(self, img_input):
        img = cv2.cvtColor(np.array(img_input), cv2.COLOR_RGB2BGR)
        processed_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        detections = []

        # Text Detection Logic
        try:
            results = self.reader.readtext(processed_img)
            for (bbox, text, conf) in results:
                (tl, tr, br, bl) = bbox
                x1, y1 = map(int, tl)
                x2, y2 = map(int, br)
                detections.append({"type": "text", "value": text, "bbox": [x1,y1,x2,y2]})
                cv2.rectangle(processed_img, (x1,y1), (x2,y2), (0,255,0), 2)
                cv2.putText(processed_img, f"Text:{text}", (x1,y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,(0,255,0),2)
        except Exception as e:
            print(f"OCR detection error: {e}")

        # Face Detection Logic
        try:
            faces = self.face_cascade.detectMultiScale(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 1.3, 5)
            for (x,y,w,h) in faces:
                detections.append({"type": "face", "bbox": [int(x),int(y),int(x+w),int(y+h)]})
                cv2.rectangle(processed_img, (x,y), (x+w,y+h), (255,0,0), 2)
                cv2.putText(processed_img, "Face", (x,y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,(255,0,0),2)
        except Exception as e:
            print(f"Face detection error: {e}")

        # QR / Barcode Detection Logic
        try:
            barcodes = decode(img)
            for bc in barcodes:
                (x,y,w,h) = bc.rect
                detections.append({"type": "qrcode", "value": bc.data.decode("utf-8"), "bbox": [x,y,x+w,y+h]})
                cv2.rectangle(processed_img, (x,y), (x+w,y+h), (0,0,255), 2)
                cv2.putText(processed_img, "QR/Barcode", (x,y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,(0,0,255),2)
        except Exception as e:
            print(f"QR/Barcode detection error: {e}")

        # YOLOv8 Object Detection (traffic signs, cars, license plates surrogate)
        try:
            results = self.yolo_model(processed_img)
            for r in results:
                for box in r.boxes:
                    cls = self.yolo_model.names[int(box.cls)]
                    conf = float(box.conf)
                    x1,y1,x2,y2 = map(int, box.xyxy[0])
                    if cls in ["stop sign", "car", "truck", "bus", "person"]:
                        detections.append({"type": f"object:{cls}", "bbox": [x1,y1,x2,y2], "conf": conf})
                        cv2.rectangle(processed_img, (x1,y1), (x2,y2), (255,255,0), 2)
                        cv2.putText(processed_img, f"{cls} {conf:.2f}", (x1,y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,(255,255,0), 2)

        except Exception as e:
            print(f"YOLO detection error: {e}")

        return processed_img, detections