# GenAI Location Privacy — Runtime Blitz (TikTok Hackathon)

**Detect and defuse location leakage from photos.**

This app lets users upload an image, infers likely geo-location cues, and lets users mask high-risk regions (e.g., license plates, road signs) to reduce precise location leakage—aligned with TikTok's hackathon brief.

## Team
- **Sukumar Ganesan** • **Amish Thekke Parambal** • **Moukthika Muthukrishnan** • **Keerthana Sundararaman** • **Vedant Rai**
- **Team name:** Runtime Blitz

---

~~## ✨ What it does (Basic Working)

### 1. Upload
User uploads a photo to `/api/scan/image`.

### 2. LLM Geo-Hypotheses
**LLMGeoGuesser** (Gemini 2.5 Flash via pydantic-ai) analyzes the image and proposes the most specific plausible location (city/landmark) with a confidence and a ranked list of location cues to look for (e.g., "street name sign", "temple gopuram", "double-decker bus").

### 3. Grounded Detection
**GroundingDinoBoundingBox** runs open-vocabulary detection with those cue phrases, returning tight bounding boxes for each cue.

Oversized boxes are filtered (`MAX_AREA_FRAC`) to avoid masking huge regions.

### 4. Geo Coordinates (Optional)
We convert the LLM's best named place into lat/lon via OpenStreetMap Nominatim (single result, throttled, user-agent set).

### 5. Privacy Transform~~

**Masking:**
- **EXIF scrub:** Strips the Metadata
- **Smart pixelation:** Mask only the detected regions (rectangle or SAM-ready hooks), with adaptive block size to hamper OCR/landmark recovery.

### 6. Return
API returns a compact JSON bundle (`GeoGuess`) with:
- Base64 preview
- Best LLM prediction (+ optional coords)
- Serialized detection map (phrases → box/logit)

A separate `/api/mask/image` call accepts those boxes to produce a final masked image.

---

## 🧱 Architecture Overview

```
FastAPI
 ├── /api/scan/image  [core pipeline]
 │     ├── LLMGeoGuesser (Gemini 2.5 Flash via pydantic-ai)
 │     ├── InferredCueOrchestrator (glue)
 │     └── GroundingDINO (open-vocab detection for LLM "cues")
 ├── /api/mask/image   [pixelate w/ EXIF scrub]
 ├── /api/scan/text    [PII text redaction: regex + spaCy]
 └── /api/health       [simple health API]
```

### Key modules
- `services/inferred_cues/llm_geoguesser.py` — System prompt & backoff; outputs LLMPredictionsResponse.
- `services/inferred_cues/grounding_dino_bounding_box.py` — Loads GroundingDINO; filters large boxes; draws/serializes outputs.
- `services/masking/masking.py` — EXIF scrub + smart pixelation.
- `services/masking/pii.py` — Regex-first PII with spaCy fallback for `/api/scan/text`.
- `services/inferred_cues/inferred_cues_orchestrator.py` — Resizing, LLM → DINO cue plumbing, OSM lookup, final packing. (service orchestration)

---

## 🔐 Privacy by Design

- **On-device friendly components:** Open-vocabulary detection (GroundingDINO) and masking run locally.
- **Metadata minimized:** Images are re-encoded before transformation to strip EXIF.
- **Targeted masking:** Only high-risk, LLM-nominated cues are masked to preserve utility while lowering re-identification risk.
- **PII text guardrail:** Separate endpoint to redact sensitive text if captions/notes are processed.
- **Gemini 2.5 APIs:** The billing-account version ensures user data remains private.

## 📦 Installation

**Requires:** Python 3.10+ (tested), Node (only if you run Playwright E2E), and a GPU is optional but recommended for faster GroundingDINO.

### 1) Clone & set up environment
```bash
git clone <your-repo-url> genai-location-privacy
cd genai-location-privacy
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2) Environment variables
Create `.env`:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3) spaCy model (for text PII fallback)
```bash
python -m spacy download en_core_web_sm
# If you have GPU and want higher quality:
# python -m spacy download en_core_web_trf
```

### 4) GroundingDINO assets
This project expects a local GroundingDINO folder with the Swin-T OGC config and a weights file:

```
services/
  GroundingDINO/
    groundingdino/
      config/GroundingDINO_SwinT_OGC.py
    weights/
      groundingdino_swint_ogc.pth
```

**Place the GroundingDINO_SwinT_OGC.py config at:**
`services/GroundingDINO/groundingdino/config/GroundingDINO_SwinT_OGC.py`

**Place the groundingdino_swint_ogc.pth weights at:**
`services/GroundingDINO/weights/groundingdino_swint_ogc.pth`

> **Tip:** If you use a different layout, update `GroundingDinoBoundingBox.CONFIG_PATH` and `WEIGHTS_PATH` accordingly.

### 5) Playwright (to scrape street view data from the web, gsv_scrapper)
```bash
pip install playwright
python -m playwright install --with-deps
# macOS without sudo:
#   python -m playwright install
# Linux CI:
#   python -m playwright install --with-deps chromium
```


---

## ▶️ Run the API

```bash
python main.py
```

**Health check:**
```bash
curl -i http://localhost:8000/api/health
```

---

## 🧪 API Usage

### 1) Scan an image (get cues + boxes + best guess)

**POST** `/api/scan/image` (form-data file upload)

```bash
curl -X POST http://localhost:8000/api/scan/image \
  -F "image=@/path/to/photo.jpg"
```

**Response (truncated example):**
```json
{
  "resized_image_bytes": "base64-...",
  "prediction": {
    "confidence": 0.73,
    "detailed_location": {
      "country": "Singapore",
      "city": "Singapore",
      "closest_likely_region": "Sri Mariamman Temple",
      "string_query_for_openstreetmap": "Sri Mariamman Temple Singapore"
    },
    "location_cues": [
      {"priority":1,"location_cue":"temple gopuram","reason":"distinctive Dravidian tower"},
      {"priority":2,"location_cue":"Tamil signage","reason":"regional language indicator"}
    ],
    "coords": {"lat":1.2829,"lon":103.844}
  },
  "bounding_box": {
    "image_bytes": "base64-annotated-preview",
    "mapping": {
      "temple gopuram": {"box":[0.51,0.32,0.28,0.46],"logit":0.86},
      "Tamil signage":  {"box":[0.18,0.77,0.20,0.08],"logit":0.64}
    }
  }
}
```

### 2) Mask the image (apply pixelation to detected boxes)

**POST** `/api/mask/image` (JSON)

```bash
curl -X POST http://localhost:8000/api/mask/image \
  -H "Content-Type: application/json" \
  -d '{
    "resized_image_bytes": "<base64-from-scan>",
    "mapping": {
      "temple gopuram": {"box":[0.51,0.32,0.28,0.46],"logit":0.86},
      "Tamil signage":  {"box":[0.18,0.77,0.20,0.08],"logit":0.64}
    }
  }'
```

**Response:**
```json
{ "masked_img": "base64-jpeg-with-pixelation" }
```

### 3) Scan text for PII (optional helper)

**POST** `/api/scan/text` (form-urlencoded)

```bash
curl -X POST http://localhost:8000/api/scan/text \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d 'text_input=My SSN is 123-45-6789'
```

---

## ⚙️ Key Config & Tuning

### GroundingDINO thresholds
- `BOX_THRESHOLD = 0.37` — higher = fewer, higher-confidence boxes.
- `TEXT_THRESHOLD = 0.25` — text phrase matching confidence.
- `MAX_AREA_FRAC = 0.25` — drop boxes covering >25% of the image to avoid over-masking.

### Masking
- `pixel_size` (default 12) is adaptive per region; increase to reduce OCR recoverability.

### LLM
- **Model:** gemini-2.5-flash
- **Temperature in code:** 0.0 for determinism
- **System prompt** enforces specific, named places and concrete cues.

---

## 📁 Data Models (Pydantic)

- `LLMPrediction{,WithLatLong}` — main hypothesis, cues, optional coords
- `SerializedBoundingBoxCoord` — serializes image + {phrase → (box, logit)}
- `GeoGuess` — scan response bundle (image preview + prediction + boxes)
- `MaskImage` — input to masking endpoint (image + mapping)

---

## 🧰 Development Tips

- **GPU:** If you have an Apple Silicon Mac, GroundingDINO code uses mps when available; on CUDA, set device accordingly.
- **Image resizing:** Orchestrator resizes to 720×540 for stable latency.
- **EXIF stripping:** Happens before pixelation; do not rely on input metadata post-pipeline.

---

## 🧭 Roadmap (Post-Hackathon)

- 🔍 **Segment-Anything masks** (already stubbed) for tight, shape-aware masking.
- 🧪 **Cue effectiveness scoring** (A/B which cues most reduce geolocation success).
- 🧱 **Noise injection variants** (dither, blur, mosaic mix) with anti-forensics.
- 🧩 **Iterative red-team loop** (re-run LLM/DINO on masked output to confirm risk reduction).
- 🌐 **Batch/offline mode** and privacy assessment reports.
- 🖥️ **Web UI** with Playwright E2E.

---

## 🚀 Quick Start (TL;DR)

```bash
# 1) env
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
echo "GEMINI_API_KEY=xxxx" > .env

# 2) models
python -m spacy download en_core_web_sm
# Place GroundingDINO config + weights under services/GroundingDINO/...

# 3) run
uvicorn app:app --host 0.0.0.0 --port 8000 --reload

# 4) test
curl -F "image=@/tmp/test.jpg" http://localhost:8000/api/scan/image
```

---

## 🙏 Acknowledgements

- **GroundingDINO** for open-vocabulary detection.
- **OpenStreetMap Nominatim** for geocoding.
- **Gemini 2.5 Flash** (via pydantic-ai) for fast location hypotheses.

---

## 📜 License

For hackathon/demo use. If open-sourcing, add a standard OSS license (MIT) and verify third-party model license compliance.

---

**Built by Runtime Blitz for the TikTok Hackathon.**