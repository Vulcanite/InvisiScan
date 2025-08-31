# GenAI Location Privacy & PII Detection System — Runtime Blitz

**Automatically detect and redact sensitive location and personal information from images and text.**
This system prioritizes hiding location-sensitive cues in images while optionally detecting and masking PII for safe data processing and sharing.

---

## 🚀 Feature Overview

The system protects user privacy by masking high-risk **location cues** in images and sensitive **PII** in text, enabling safe sharing and compliance with privacy requirements.

### Core Features

* **Location-Sensitive Masking**: Identify and pixelate regions revealing location (license plates, street signs, landmarks).
* **Hybrid Detection Engine**: LLM + GroundingDINO for images; regex + spaCy NLP for text.
* **Real-Time Processing**: Optimized APIs for high-throughput workloads.
* **Targeted Masking**: Only sensitive regions are redacted to preserve utility.
* **Optional PII Detection**: Detect and redact text-based personally identifiable information.

---

## 🌟 Key Functionality

### Hiding Location-Sensitive Cues

1. **Upload Image**: Accept images via `/api/scan/image`.
2. **LLM Geo-Hypotheses**: Gemini 2.5 Flash predicts the most likely location and cues.
3. **Grounded Detection**: GroundingDINO detects LLM-nominated cues (street signs, license plates, landmarks).
4. **Privacy Transform**: Smart pixelation of sensitive regions and EXIF metadata stripping.
5. **Optional Geo Coordinates**: Convert named locations to lat/lon via OpenStreetMap.
6. **Return Response**: Base64 preview, predicted location, serialized detection map.

### PII Detection

1. **Text Analysis**: Detect PII in user-provided text via `/api/scan/text`.
2. **Entity Prioritization**: Resolve overlapping or conflicting detections.
3. **Redaction Output**: Replace sensitive information with `<ENTITY_TYPE>` placeholders.
4. **Detailed Reporting**: Confidence scores, entity counts, and detection sources.

---

## 🧱 Technical Architecture

```
FastAPI
 ├── /api/scan/image    [Location-sensitive detection]
 │     ├── LLMGeoGuesser (Gemini 2.5)
 │     ├── InferredCueOrchestrator
 │     └── GroundingDINO (open-vocab detection)
 ├── /api/mask/image    [Smart pixelation + EXIF scrub]
 ├── /api/scan/text     [PII text detection]
 │     ├── Regex Engine (US patterns)
 │     └── spaCy NER (contextual)
 ├── /api/healthz       [Health check]
```

### Supported Detection Types

**Location-Sensitive Image Cues:**

* License Plates, Street Signs, Landmarks, Storefronts

**Text PII:**

* **Regex (US-Focused):** SSN, Credit Cards, Phone Numbers, Emails, Driver Licenses, Bank Accounts, Addresses, ZIP Codes, Passport Numbers
* **spaCy (Contextual):** Person Names, Organizations, Locations, Dates/Times, Monetary Values

---

## 🛠 Development Tools

### Core Framework

* **FastAPI** — API endpoints with automatic docs
* **Uvicorn** — ASGI server
* **Python 3.10+** — Runtime environment

### Libraries

```python
# NLP & Detection
spacy==3.8.7
transformers==4.56.0  # optional for NLP

# Web Framework
fastapi==0.116.1
uvicorn==0.35.0
python-multipart==0.0.20

# Image Processing
pillow==11.3.0
opencv-python==4.12.0.88
easyocr==1.7.2

# Utilities
pydantic==2.11.7
regex==2025.8.29
typing-extensions==4.15.0
```

### spaCy Models

* `en_core_web_trf` — Transformer-based model (\~500MB)
* `en_core_web_sm` — Compact fallback (\~15MB)

### System Dependencies

* **Tesseract OCR** — Image text extraction
* **CUDA/GPU** (optional) — Transformer acceleration

---

## 🔧 API Endpoints

| Endpoint          | Method | Description                                       |
| ----------------- | ------ | ------------------------------------------------- |
| `/api/scan/image` | POST   | Detect and mask location-sensitive cues in images |
| `/api/mask/image` | POST   | Apply smart pixelation and EXIF scrub             |
| `/api/scan/text`  | POST   | Detect and redact PII in text                     |
| `/api/healthz`    | GET    | Check system health                               |

---

## ⚙️ Detection Strategy

### Location-Sensitive Cues

* **LLMGeoGuesser**: Infers likely city/landmark and cue phrases.
* **GroundingDINO**: Open-vocabulary detection of sensitive image regions.
* **Masking**: Pixelation, EXIF stripping, optional SAM integration.

### PII Text

* **Regex-first**: Fast detection for structured PII (SSN, credit cards).
* **spaCy NLP**: Contextual backup for unstructured entities (names, locations).

---

## 📊 Performance

* **Text Response Time**: \~200ms typical
* **Memory Usage**: 50MB (compact) – 500MB (transformer)
* **Image Detection**: \~1–3s per image (GPU recommended)
* **Throughput**: 50+ requests/sec for text, 5–10/sec for images (CPU)

---

## 📦 Project Setup (Linux Environment)


```bash
git clone https://github.com/Vulcanite/InvisiScan

# Visual Cues Feature Setup
cd InvisiScan/api
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

mkdir -p GroundingDINO/weights && curl -sL https://github.com/IDEA-Research/GroundingDINO/releases/download/v0.1.0-alpha/groundingdino_swint_ogc.pth -o GroundingDINO/weights/groundingdino_swint_ogc.pth

# PII Detection Feature Setup

## spaCy models
python -m spacy download en_core_web_sm
python -m spacy download en_core_web_trf

# Frontend Setup

cd ..
npm install
npm run dev
```

Set environment variables:

```env
GEMINI_API_KEY=<your_api_key_here>
```

Run the API:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Test endpoints:

```bash
curl -F "image=@/tmp/test.jpg" http://localhost:8000/api/scan/image
curl -X POST -d 'text_input=My SSN is 123-45-6789' http://localhost:8000/api/scan/text
```

---

## 🙏 Acknowledgements

* **GroundingDINO** — Open-vocabulary detection
* **OpenStreetMap Nominatim** — Geocoding
* **Gemini 2.5 Flash** — LLM-based location hypotheses
* **spaCy** — NLP-based PII detection

---

**Built by Runtime Blitz for the TikTok TechJam 2025 Hackathon**