import io
import base64
from PIL import Image
from fastapi import UploadFile, HTTPException
from object_detection import ObjectDetector

async def process_image(image: UploadFile):
    """Clean EXIF data and run object detection on an image."""
    if not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid file type. Upload an image.")

    content = await image.read()
    pil_img = Image.open(io.BytesIO(content))
    clean_img = Image.new(pil_img.mode, pil_img.size)
    clean_img.putdata(list(pil_img.getdata()))
    try:
        detector = ObjectDetector()
        img_rgb, detections = detector.detect_cues(pil_img)
    except Exception as e:
        print(f"Object detection failed: {e}")
        img_rgb, detections = [], []

    width, height = pil_img.size
    buffered = io.BytesIO()
    Image.fromarray(img_rgb.astype("uint8")).save(buffered, format="PNG")

    return {
        "message": "Image processed successfully (EXIF removed).",
        "data": {
            "original_filename": image.filename,
            "image_size": {"width": width, "height": height},
            "file_size": len(content),
            "format": pil_img.format,
            "mode": pil_img.mode,
            "processing_status": "completed",
            "input_type": "image",
            "object_detections": detections,
        },
        "processed_image": {
            "base64": base64.b64encode(buffered.getvalue()).decode("utf-8"),
            "content_type": image.content_type,
        },
    }
