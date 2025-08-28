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
        # Create a clean copy without EXIF data
        clean_image = Image.new(pil_image.mode, pil_image.size)
        clean_image.putdata(list(pil_image.getdata()))
    
        # Save to BytesIO without metadata - this strips the exif data
        output = io.BytesIO()
        clean_image.save(output, format=pil_image.format, optimize=True)

        output.seek(0)
        
        width, height = pil_image.size
        img_base64 = base64.b64encode(output.read()).decode('utf-8')

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