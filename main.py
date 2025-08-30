from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from pii import pii_detector
from image_processor import process_image

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/scan")
async def scan_data(image: UploadFile = File(None), text_input: str = Form(None)):
    """Scan images or text for sensitive information."""
    try:
        if image and image.filename:
            return JSONResponse(await process_image(image))
        elif text_input and text_input.strip():
            return JSONResponse(pii_detector.process_text(text_input))
        else:
            raise HTTPException(status_code=400, detail="Provide an image or text input.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@app.get("/api/supported-entities")
async def get_supported_entities():
    presidio_entities = pii_detector.analyzer.get_supported_entities(language="en")
    distilbert_entities = ["NER_PER", "NER_LOC", "NER_ORG", "NER_MISC"]
    return JSONResponse({
        "presidio_entities": presidio_entities,
        "distilbert_entities": distilbert_entities,
        "total_supported": len(presidio_entities) + len(distilbert_entities),
    })

@app.get("/api/model-status")
async def get_model_status():
    return JSONResponse({
        "presidio_status": "initialized" if pii_detector.analyzer else "failed",
        "distilbert_status": "initialized" if pii_detector.ner_pipeline else "failed",
        "device": pii_detector.device,
    })
