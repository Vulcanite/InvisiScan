from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
from pathlib import Path

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@app.post("/api/upload")
async def upload_image(image: UploadFile = File(...)):
    try:
        if not image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Invalid file type. Please upload an image.")

        file_path = UPLOAD_DIR / image.filename
        with open(file_path, "wb") as f:
            content = await image.read()
            f.write(content)

        return JSONResponse({"message": "Upload successful!", "filename": image.filename})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")