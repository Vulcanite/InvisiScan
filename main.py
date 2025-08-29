from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import base64
from PIL import Image
import io
from typing import Optional
from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_anonymizer import AnonymizerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Presidio engines
def initialize_presidio():
    """Initialize Presidio analyzer and anonymizer engines"""
    try:
        # Create NLP engine configuration for spaCy
        nlp_configuration = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}]
        }
        
        # Create NLP engine
        nlp_engine_provider = NlpEngineProvider(nlp_configuration=nlp_configuration)
        nlp_engine = nlp_engine_provider.create_engine()
        
        # Initialize analyzer and anonymizer
        #analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
        #anonymizer = AnonymizerEngine()

        hcn_pattern = Pattern(
        name="HCN Pattern",
        regex=r"\bHCN[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{3}\b",
        score=0.9,
        )

        health_id_recognizer = PatternRecognizer(
            supported_entity="HEALTH_INSURANCE_ID",
            patterns=[hcn_pattern]
        )

        #US SSN fallback
        ssn_pattern = Pattern(
            name="US_SSN_FALLBACK",
            regex=r"\b\d{3}-\d{2}-\d{4}\b",
            score=0.95
        )
        ssn_recognizer = PatternRecognizer(
            supported_entity="US_SSN",
            patterns=[ssn_pattern]
        )


        # Analyzer with custom recognizers
        analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
        analyzer.registry.add_recognizer(health_id_recognizer)
        analyzer.registry.add_recognizer(ssn_recognizer)
        #analyzer.registry.add_recognizer(address_recognizer)
        anonymizer = AnonymizerEngine()

        
        return analyzer, anonymizer
    except Exception as e:
        print(f"Warning: Could not initialize Presidio with spaCy model. Using default configuration. Error: {e}")
        # Fallback to default configuration
        analyzer = AnalyzerEngine()
        anonymizer = AnonymizerEngine()
        return analyzer, anonymizer

# Global Presidio engines
analyzer, anonymizer = initialize_presidio()

def detect_and_redact_pii(text: str) -> dict:
    """
    Detect and redact PII from text using Microsoft Presidio
    
    Args:
        text (str): Input text to analyze
        
    Returns:
        dict: Dictionary containing redacted text and analysis results
    """
    try:
        # Define entities to detect - you can customize this list
        entities_to_detect = [
            "PERSON",
            "EMAIL_ADDRESS", 
            "PHONE_NUMBER",
            "CREDIT_CARD",
            "IBAN_CODE",
            "IP_ADDRESS",
            "LOCATION",
            "DATE_TIME",
            "NRP",  # National Registration Number
            "MEDICAL_LICENSE",
            "URL",
            "US_DRIVER_LICENSE",
            "US_PASSPORT",
            "CRYPTO",
            "US_ITIN",
            "US_BANK_NUMBER",
            "US_SSN",
            "UK_NHS",
            "UK,NINO",
            "SG_NRIC_FIN",
            "SG_UEN",
            "IN_PAN",
            "IN_PASSPORT",
            "IN_VOTER",
            "IN_VEHICLE_REGISTRATION"
        ]
        
        # Analyze text for PII
        analysis_results = analyzer.analyze(
            text=text,
            entities=entities_to_detect,
            language='en'
        )
        
        
        # Anonymize/redact the detected PII
        anonymized_result = anonymizer.anonymize(
            text=text,
            analyzer_results=analysis_results
        )
        
        # Prepare analysis summary
        detected_entities = {}
        for result in analysis_results:
            entity_type = result.entity_type
            if entity_type not in detected_entities:
                detected_entities[entity_type] = 0
            detected_entities[entity_type] += 1
        
        return {
            "redacted_text": anonymized_result.text,
            "original_length": len(text),
            "redacted_length": len(anonymized_result.text),
            "detected_entities": detected_entities,
            "total_entities_found": len(analysis_results),
            "analysis_results": [
                {
                    "entity_type": result.entity_type,
                    "start": result.start,
                    "end": result.end,
                    "score": round(result.score, 3)
                }
                for result in analysis_results
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PII detection failed: {str(e)}")

@app.post("/api/scan")
async def scan_data(
    image: Optional[UploadFile] = File(None),
    text_input: Optional[str] = Form(None)
):
    """
    Unified endpoint to scan both images and text for sensitive information
    """
    try:
        # Determine input type and process accordingly
        if image and image.filename:
            # Handle image processing
            if not image.content_type.startswith("image/"):
                raise HTTPException(status_code=400, detail="Invalid file type. Please upload an image.")

            content = await image.read()
            pil_image = Image.open(io.BytesIO(content))
            
            # Create a clean copy without EXIF data (removes metadata)
            clean_image = Image.new(pil_image.mode, pil_image.size)
            clean_image.putdata(list(pil_image.getdata()))
        
            # Save to BytesIO without metadata
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
                "processing_status": "completed",
                "input_type": "image"
            }

            return JSONResponse({
                "message": "Image processing successful! EXIF data removed.",
                "data": processing_data,
                "processed_image": {
                    "base64": img_base64,
                    "content_type": image.content_type
                }
            })

        elif text_input and text_input.strip():
            # Handle text processing with Presidio
            pii_analysis = detect_and_redact_pii(text_input.strip())
            
            processing_data = {
                "file_size": len(text_input.encode('utf-8')),
                "format": "text",
                "processing_status": "completed",
                "input_type": "text",
                "original_length": pii_analysis["original_length"],
                "redacted_length": pii_analysis["redacted_length"],
                "entities_detected": pii_analysis["detected_entities"],
                "total_entities_found": pii_analysis["total_entities_found"]
            }

            return JSONResponse({
                "message": f"Text analysis completed! Found and redacted {pii_analysis['total_entities_found']} sensitive entities.",
                "data": processing_data,
                "redacted_text": pii_analysis["redacted_text"],
                "analysis_summary": {
                    "detected_entities": pii_analysis["detected_entities"],
                    "analysis_results": pii_analysis["analysis_results"]
                }
            })

        else:
            raise HTTPException(status_code=400, detail="Please provide either an image file or text input.")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@app.get("/api/supported-entities")
async def get_supported_entities():
    """Get list of supported PII entities that can be detected"""
    try:
        supported_entities = analyzer.get_supported_entities(language='en')
        
        return JSONResponse({
            "supported_entities": supported_entities,
            "total_count": len(supported_entities)
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not retrieve supported entities: {str(e)}")