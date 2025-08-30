import cv2
import matplotlib.pyplot as plt
import easyocr
from pyzbar.pyzbar import decode
from ultralytics import YOLO
import numpy as np
from PIL import Image


class ObjectDetector:
    def __init__(self):  # Fixed: Added 'self' parameter
        self.reader = easyocr.Reader(['en'])
        # OpenCV Face Detector (Haar cascade)
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        # YOLOv8 (pretrained on COCO, which has traffic signs, cars, etc.)
        self.yolo_model = YOLO("yolov8n.pt")   # lightweight model

    # --- Detection function ---
    def detect_cues(self, image_input):  # Changed to accept different input types
        # Handle different input types
        if isinstance(image_input, str):
            # If it's a file path
            img = cv2.imread(image_input)
        elif isinstance(image_input, Image.Image):
            # If it's a PIL Image
            img = cv2.cvtColor(np.array(image_input), cv2.COLOR_RGB2BGR)
        elif isinstance(image_input, np.ndarray):
            # If it's already a numpy array
            img = image_input
        else:
            raise ValueError("Unsupported image input type")
            
        if img is None:
            return []
            
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        detections = []

        # 1. OCR (text detection)
        try:
            results = self.reader.readtext(img_rgb)
            for (bbox, text, conf) in results:
                (tl, tr, br, bl) = bbox
                x1, y1 = map(int, tl)
                x2, y2 = map(int, br)
                detections.append({"type": "text", "value": text, "bbox": [x1,y1,x2,y2]})
                cv2.rectangle(img_rgb, (x1,y1), (x2,y2), (0,255,0), 2)
                cv2.putText(img_rgb, f"Text:{text}", (x1,y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,(0,255,0),2)
        except Exception as e:
            print(f"OCR detection error: {e}")

        # 2. Face Detection
        try:
            faces = self.face_cascade.detectMultiScale(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 1.3, 5)
            for (x,y,w,h) in faces:
                detections.append({"type": "face", "bbox": [int(x),int(y),int(x+w),int(y+h)]})
                cv2.rectangle(img_rgb, (x,y), (x+w,y+h), (255,0,0), 2)
                cv2.putText(img_rgb, "Face", (x,y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,(255,0,0),2)
        except Exception as e:
            print(f"Face detection error: {e}")

        # 3. QR / Barcode Detection
        try:
            barcodes = decode(img)
            for bc in barcodes:
                (x,y,w,h) = bc.rect
                detections.append({"type": "qrcode", "value": bc.data.decode("utf-8"), "bbox": [x,y,x+w,y+h]})
                cv2.rectangle(img_rgb, (x,y), (x+w,y+h), (0,0,255), 2)
                cv2.putText(img_rgb, "QR/Barcode", (x,y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,(0,0,255),2)
        except Exception as e:
            print(f"QR/Barcode detection error: {e}")

        # 4. YOLOv8 Object Detection (traffic signs, cars, license plates surrogate)
        try:
            results = self.yolo_model(img_rgb)
            for r in results:
                for box in r.boxes:
                    cls = self.yolo_model.names[int(box.cls)]
                    conf = float(box.conf)
                    x1,y1,x2,y2 = map(int, box.xyxy[0])
                    if cls in ["stop sign","car","truck","bus","person"]:   # extend with other classes if needed
                        detections.append({"type": f"object:{cls}", "bbox": [x1,y1,x2,y2], "conf": conf})
                        cv2.rectangle(img_rgb, (x1,y1), (x2,y2), (255,255,0), 2)
                        cv2.putText(img_rgb, f"{cls} {conf:.2f}", (x1,y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5,(255,255,0), 2)

        except Exception as e:
            print(f"YOLO detection error: {e}")

        plt.figure(figsize=(10,10))
        plt.imshow(img_rgb)
        plt.axis("off")
        plt.show()

        return img_rgb, detections