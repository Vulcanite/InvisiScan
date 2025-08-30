from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import base64
from PIL import Image
import io
from typing import Optional, List, Dict, Tuple
import re
from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_anonymizer import AnonymizerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider
from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline
import torch
from object_detection import ObjectDetector

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class UnifiedPIIDetector:
    """Unified PII detection combining Presidio and DistilBERT without conflicts"""
    
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = None
        self.model = None
        self.ner_pipeline = None
        self.analyzer = None
        self.anonymizer = None
        self.initialize_models()
    
    def initialize_models(self):
        """Initialize both Presidio and DistilBERT models"""
        try:
            # Initialize DistilBERT NER
            ner_model_name = "dslim/distilbert-NER"
            self.ner_pipeline = pipeline(
                "ner", 
                model=ner_model_name, 
                tokenizer=ner_model_name,
                aggregation_strategy="simple",
                device=0 if self.device == "cuda" else -1
            )
            print(f"DistilBERT initialized on {self.device}")
            
            # Initialize Presidio with enhanced patterns
            self.analyzer, self.anonymizer = self._initialize_presidio()
            print("Presidio initialized with custom patterns")
            
        except Exception as e:
            print(f"Model initialization error: {e}")
            # Fallback initialization
            self.analyzer = AnalyzerEngine()
            self.anonymizer = AnonymizerEngine()
    
    def _initialize_presidio(self):
        """Initialize Presidio with comprehensive custom patterns"""
        try:
            # Create NLP engine configuration
            nlp_configuration = {
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}]
            }
            
            nlp_engine_provider = NlpEngineProvider(nlp_configuration=nlp_configuration)
            nlp_engine = nlp_engine_provider.create_engine()
            
            # Enhanced Health Card Number patterns
            hcn_patterns = [
                Pattern(name="HCN_STANDARD", regex=r"\bHCN[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{3}\b", score=0.9),
                Pattern(name="HCN_SIMPLE", regex=r"\b\d{3}[-\s]?\d{3}[-\s]?\d{3}\b", score=0.7)
            ]
            hcn_recognizer = PatternRecognizer(
                supported_entity="HEALTH_INSURANCE_ID",
                patterns=hcn_patterns
            )
            
            # Enhanced SSN patterns
            ssn_patterns = [
                Pattern(name="US_SSN_DASHES", regex=r"\b\d{3}-\d{2}-\d{4}\b", score=0.95),
                Pattern(name="US_SSN_SPACES", regex=r"\b\d{3}\s\d{2}\s\d{4}\b", score=0.95),
                Pattern(name="US_SSN_CONTINUOUS", regex=r"\b\d{9}\b", score=0.8)
            ]
            ssn_recognizer = PatternRecognizer(
                supported_entity="US_SSN",
                patterns=ssn_patterns
            )
            
            # Enhanced Address patterns
            address_patterns = [
                Pattern(
                    name="US_ADDRESS_COMPLETE", 
                    regex=r'\b\d{1,6}\s+[\w\s\.-]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Circle|Cir|Way|Terrace|Ter|Place|Pl)\b[,\s]*[\w\s]*[,\s]*(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\s+\d{5}(?:-\d{4})?\b',
                    score=0.9
                ),
                Pattern(
                    name="PARTIAL_ADDRESS", 
                    regex=r'\b\d{1,6}\s+[\w\s\.-]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Circle|Cir|Way|Terrace|Ter|Place|Pl)\b',
                    score=0.8
                )
            ]
            address_recognizer = PatternRecognizer(
                supported_entity="ADDRESS",
                patterns=address_patterns
            )
            
            # Bank routing number pattern regex
            routing_patterns = [
                Pattern(name="ROUTING_NUMBER", regex=r'\b\d{9}\b', score=0.75)
            ]
            routing_recognizer = PatternRecognizer(
                supported_entity="US_BANK_NUMBER",
                patterns=routing_patterns
            )
            
            # Account number pattern (generic)
            account_patterns = [
                Pattern(name="ACCOUNT_NUMBER", regex=r'\bAcct:?\s*\d{8,20}\b', score=0.85),
                Pattern(name="ACCOUNT_SIMPLE", regex=r'\b\d{10,20}\b', score=0.6)
            ]
            account_recognizer = PatternRecognizer(
                supported_entity="ACCOUNT_NUMBER",
                patterns=account_patterns
            )
            phone_patterns = [
                Pattern(name="US_PHONE", regex=r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", score=0.9),
                Pattern(name="INTL_PHONE", regex=r"\b\+?\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b", score=0.8)
            ]
            phone_recognizer = PatternRecognizer(
                supported_entity="PHONE_NUMBER",
                patterns=phone_patterns
            )
            
            # Initialize analyzer with custom recognizers
            analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
            analyzer.registry.add_recognizer(hcn_recognizer)
            analyzer.registry.add_recognizer(ssn_recognizer)
            analyzer.registry.add_recognizer(address_recognizer)
            analyzer.registry.add_recognizer(routing_recognizer)
            analyzer.registry.add_recognizer(account_recognizer)
            analyzer.registry.add_recognizer(phone_recognizer)
            
            anonymizer = AnonymizerEngine()
            return analyzer, anonymizer
            
        except Exception as e:
            print(f"Presidio initialization error: {e}")
            return AnalyzerEngine(), AnonymizerEngine()
    
    def detect_comprehensive_pii(self, text: str) -> dict:
        """
        Comprehensive PII detection using unified approach
        """
        try:
            # Step 1: Get all entities from both systems
            presidio_entities = self._get_presidio_entities(text)
            distilbert_entities = self._get_distilbert_entities(text) if self.ner_pipeline else []
            
            # Step 2: Merge and deduplicate entities
            unified_entities = self._merge_entities(presidio_entities, distilbert_entities)
            
            # Step 3: Apply unified redaction
            final_redacted_text = self._apply_unified_redaction(text, unified_entities)
            
            # Step 4: Create comprehensive summary
            entity_summary = self._create_entity_summary(unified_entities)
            
            return {
                "original_text": text,
                "redacted_text": final_redacted_text,
                "entities_found": len(unified_entities),
                "entity_summary": entity_summary,
                "all_entities": unified_entities,
                "redaction_success": True
            }
            
        except Exception as e:
            return {
                "original_text": text,
                "redacted_text": text,  # Return original if processing fails
                "entities_found": 0,
                "entity_summary": {},
                "all_entities": [],
                "redaction_success": False,
                "error": str(e)
            }
    
    def _get_presidio_entities(self, text: str) -> List[Dict]:
        """Get entities from Presidio"""
        entities_to_detect = [
            "PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD",
            "LOCATION", "DATE_TIME", "US_SSN", "US_DRIVER_LICENSE",
            "HEALTH_INSURANCE_ID", "ADDRESS", "US_BANK_NUMBER", "ACCOUNT_NUMBER",
            "URL", "IP_ADDRESS", "CRYPTO", "MEDICAL_LICENSE"
        ]
        
        results = self.analyzer.analyze(
            text=text,
            entities=entities_to_detect,
            language='en'
        )
        
        entities = []
        for result in results:
            entities.append({
                "start": result.start,
                "end": result.end,
                "entity_type": result.entity_type,
                "confidence": result.score,
                "text": text[result.start:result.end],
                "source": "presidio"
            })
        
        return entities
    
    def _get_distilbert_entities(self, text: str) -> List[Dict]:
        """Get entities from DistilBERT"""
        try:
            raw_entities = self.ner_pipeline(text)
            entities = []
            
            for entity in raw_entities:
                if entity['score'] > 0.7:  # High confidence only
                    entities.append({
                        "start": int(entity['start']),
                        "end": int(entity['end']),
                        "entity_type": f"NER_{entity['entity_group']}",
                        "confidence": float(entity['score']),
                        "text": text[int(entity['start']):int(entity['end'])],
                        "source": "distilbert"
                    })
            
            return entities
        except:
            return []
    
    def _merge_entities(self, presidio_entities: List[Dict], distilbert_entities: List[Dict]) -> List[Dict]:
        """Merge entities from both sources, removing duplicates and conflicts"""
        all_entities = presidio_entities + distilbert_entities
        
        # Sort by start position
        all_entities.sort(key=lambda x: x['start'])
        
        # Remove overlaps - prioritize higher confidence and Presidio for PII
        merged = []
        for entity in all_entities:
            overlaps = False
            for existing in merged:
                if self._entities_overlap(entity, existing):
                    overlaps = True
                    # Keep the better entity (higher confidence, or presidio for PII)
                    if (entity['confidence'] > existing['confidence'] or 
                        (entity['source'] == 'presidio' and existing['source'] == 'distilbert')):
                        merged.remove(existing)
                        merged.append(entity)
                    break
            
            if not overlaps:
                merged.append(entity)
        
        # Sort final list by start position
        merged.sort(key=lambda x: x['start'])
        return merged
    
    def _entities_overlap(self, entity1: Dict, entity2: Dict) -> bool:
        """Check if two entities overlap"""
        start1, end1 = entity1['start'], entity1['end']
        start2, end2 = entity2['start'], entity2['end']
        return not (end1 <= start2 or start1 >= end2)
    
    def _apply_unified_redaction(self, text: str, entities: List[Dict]) -> str:
        """Apply redaction using unified entity list"""
        if not entities:
            return text
        
        # Sort entities by start position in reverse order
        entities_sorted = sorted(entities, key=lambda x: x['start'], reverse=True)
        
        redacted_text = text
        for entity in entities_sorted:
            start, end = entity['start'], entity['end']
            entity_type = entity['entity_type']
            
            # Create replacement text
            replacement = f"<{entity_type.upper()}>"
            redacted_text = redacted_text[:start] + replacement + redacted_text[end:]
        
        return redacted_text
    
    def _create_entity_summary(self, entities: List[Dict]) -> Dict:
        """Create summary of detected entities"""
        summary = {}
        for entity in entities:
            entity_type = entity['entity_type']
            summary[entity_type] = summary.get(entity_type, 0) + 1
        return summary

# Global PII detector instance
pii_detector = UnifiedPIIDetector()

@app.post("/api/scan")
async def scan_data(
    image: Optional[UploadFile] = File(None),
    text_input: Optional[str] = Form(None)
):
    """
    Unified endpoint to scan both images and text for sensitive information
    """
    try:
        if image and image.filename:
            if not image.content_type.startswith("image/"):
                raise HTTPException(status_code=400, detail="Invalid file type. Please upload an image.")

            content = await image.read()
            pil_image = Image.open(io.BytesIO(content))

            clean_image = Image.new(pil_image.mode, pil_image.size)
            clean_image.putdata(list(pil_image.getdata()))
        
            output = io.BytesIO()
            clean_image.save(output, format=pil_image.format, optimize=True)
            output.seek(0)

            try:
                object_detector = ObjectDetector()  # Fixed: Added parentheses
                img_rgb, detections = object_detector.detect_cues(pil_image)  # Pass the actual image, not a path
                print(detections)
            except Exception as e:
                print(f"Object detection failed: {e}")
                img_rgb = []  # Continue without object detection if it fails

            width, height = pil_image.size
            buffered = io.BytesIO()
            img_pil = Image.fromarray(img_rgb.astype("uint8"))
            img_pil.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

            processing_data = {
                "original_filename": image.filename,
                "image_size": {"width": width, "height": height},
                "file_size": len(content),
                "format": pil_image.format,
                "mode": pil_image.mode,
                "processing_status": "completed",
                "input_type": "image",
                "object_detections": detections  # Include detection results
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
            # Handle text processing with unified PII detection
            pii_results = pii_detector.detect_comprehensive_pii(text_input.strip())
            
            processing_data = {
                "file_size": len(text_input.encode('utf-8')),
                "format": "text",
                "processing_status": "completed" if pii_results["redaction_success"] else "failed",
                "input_type": "text",
                "original_length": len(text_input),
                "redacted_length": len(pii_results["redacted_text"]),
                "entities_detected": pii_results["entity_summary"],
                "total_entities_found": pii_results["entities_found"]
            }

            message = f"Text analysis completed! Found and redacted {pii_results['entities_found']} sensitive entities."
            if not pii_results["redaction_success"]:
                message += f" Warning: {pii_results.get('error', 'Unknown error occurred')}"

            return JSONResponse({
                "message": message,
                "data": processing_data,
                "redacted_text": pii_results["redacted_text"],
                "analysis_summary": {
                    "entities_by_type": pii_results["entity_summary"],
                    "detailed_entities": pii_results["all_entities"],
                    "redaction_success": pii_results["redaction_success"]
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
    """Get list of supported PII entities"""
    try:
        presidio_entities = pii_detector.analyzer.get_supported_entities(language='en')
        distilbert_entities = ["NER_PER", "NER_LOC", "NER_ORG", "NER_MISC"]
        
        return JSONResponse({
            "presidio_entities": presidio_entities,
            "distilbert_entities": distilbert_entities,
            "total_supported": len(presidio_entities) + len(distilbert_entities),
            "processing_pipeline": ["Unified Entity Detection", "Conflict Resolution", "Single-Pass Redaction"]
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not retrieve supported entities: {str(e)}")

@app.get("/api/model-status")
async def get_model_status():
    """Get status of detection models"""
    return JSONResponse({
        "presidio_status": "initialized" if pii_detector.analyzer else "failed",
        "distilbert_status": "initialized" if pii_detector.ner_pipeline else "failed",
        "device": pii_detector.device,
        "cuda_available": torch.cuda.is_available(),
        "unified_detector": "active"
    })