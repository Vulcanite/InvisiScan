import base64

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.settings import ModelSettings

from services.masking.masking import Masking
from services.masking.pii import pii_detector
from services.inferred_cues.grounding_dino_bounding_box import GroundingDinoBoundingBox
from services.inferred_cues.inferred_cues_orchestrator import InferredCueOrchestrator
from services.inferred_cues.llm_geoguesser import LLMGeoGuesser
from services.models import MaskImage
from services.settings import Settings

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/scan/image")
def scan_image(image: UploadFile = File(None)):
    """Scan images or text for sensitive information."""
    try:
        settings = Settings()
        provider = GoogleProvider(api_key=settings.GEMINI_API_KEY)
        model = GoogleModel('gemini-2.5-flash', provider=provider)

        agent = LLMGeoGuesser(
            google_model=model,
            settings=ModelSettings(temperature=0.0)
        )
        model = GroundingDinoBoundingBox()

        orchestrator = InferredCueOrchestrator(agent=agent, model=model)

        if not image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Invalid file type. Upload an image.")

        image_bytes = image.file.read()  # sync read
        return orchestrator.orchestrate(image_bytes)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@app.post("/api/scan/text")
def scan_text(text_input: str = Form(None)):
    try:
        if not text_input or not text_input.strip():
            raise HTTPException(status_code=400, detail="Text input is required.")

        return JSONResponse(pii_detector.process_text(text_input.strip()))

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Text processing failed: {str(e)}")


@app.post("/api/mask/image")
def mask_image(mask_image: MaskImage):
    image_bytes = mask_image.to_torch()["resized_image_bytes"]
    all_boxes = mask_image.to_torch()["boxes"]

    mask_service = Masking()
    exif_scrubbed_image_bytes = mask_service.scrub_exif_bytes(image_bytes)

    nparr = np.frombuffer(exif_scrubbed_image_bytes, np.uint8)
    image_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    pixelated_bgr = mask_service.pixelate_marked_regions(
        image_bgr=image_bgr,
        boxes_norm=all_boxes,
        pixel_size=12,
        use_sam_masks=False
    )

    return {"masked_img": base64.b64encode(pixelated_bgr).decode("utf-8")}


@app.get("/api/health")
def get_model_status():
    return Response(status_code=200)


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
