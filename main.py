from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import base64
from PIL import Image
import io

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/upload")
async def upload_image(image: UploadFile = File(...)):
    try:
        if not image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Invalid file type. Please upload an image.")

        content = await image.read()

        pil_image = Image.open(io.BytesIO(content))
        width, height = pil_image.size

        img_base64 = base64.b64encode(content).decode('utf-8')

        processing_data = {
            "original_filename": image.filename,
            "image_size": {
                "width": width,
                "height": height
            },
            "file_size": len(content),
            "format": pil_image.format,
            "mode": pil_image.mode,
            "processing_status": "completed"
        }

        return JSONResponse({
            "message": "Upload and processing successful!",
            "data": processing_data,
            "processed_image": {
                "base64": img_base64,
                "content_type": image.content_type
            }
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")