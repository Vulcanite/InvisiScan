from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import base64
from PIL import Image
import io
from typing import Optional, List, Dict
import re
import spacy

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RegexFirstPIIDetector:
    """Regex-first PII detection with spaCy backup"""
    
    def __init__(self):
        self.nlp = None
        self.initialize_spacy()
        self.regex_patterns = self._setup_regex_patterns()
    
    def initialize_spacy(self):
        """Initialize spaCy model"""
        try:
            try:
                self.nlp = spacy.load("en_core_web_trf")
                print("Loaded spaCy transformer model")
            except IOError:
                self.nlp = spacy.load("en_core_web_sm")
                print("Loaded spaCy standard model")
        except IOError:
            raise Exception("spaCy model not found. Install with: python -m spacy download en_core_web_sm")
    
    def _setup_regex_patterns(self):
        """Setup comprehensive regex patterns for structured PII"""
        return {
            "US_SSN": [
                r'\b\d{3}-\d{2}-\d{4}\b',
                r'\b\d{3}\s\d{2}\s\d{4}\b',
                r'\bSSN:?\s*(\d{3}-\d{2}-\d{4})\b'
            ],
            "PHONE_NUMBER": [
                r'\(\d{3}\)\s*\d{3}[-\s]?\d{4}',
                r'\b\d{3}-\d{3}-\d{4}\b',
                r'\b\d{3}\.\d{3}\.\d{4}\b',
                r'\+1\s?\d{3}[-\.\s]?\d{3}[-\.\s]?\d{4}'
            ],
            "HEALTH_INSURANCE_ID": [
                r'\bHCN[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{3}\b',
                r'\b\d{3}-\d{3}-\d{3}\b'
            ],
            "CREDIT_CARD": [
                r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
                r'\b\d{13,19}\b'
            ],
            "EMAIL_ADDRESS": [
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            ],
            "ADDRESS": [
                # Complete US address: street + city + state + ZIP
                r'\b\d{1,6}\s+[A-Za-z0-9\s\.-]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Circle|Cir|Way|Terrace|Ter|Place|Pl|Plaza|Pkwy|Parkway)\s*,\s*[A-Za-z\s]+,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?\b',
                # Street address only (fallback)
                r'\b\d{1,6}\s+[A-Za-z0-9\s\.-]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Circle|Cir|Way|Terrace|Ter|Place|Pl|Plaza|Pkwy|Parkway)(?:\s*,?\s*(?:Apt|Apartment|Suite|Ste|Unit|#)\s*[A-Za-z0-9-]+)?\b',
                # PO Box addresses
                r'\bP\.?O\.?\s*Box\s+\d+\b',
                # City, State ZIP pattern (for cases where street is separate)
                r'\b[A-Za-z\s]{2,30},\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?\b'
            ],
            "ZIP_CODE": [
                # More specific ZIP patterns to reduce false positives
                r'\b\d{5}-\d{4}\b',  # ZIP+4 format first
                r'(?<!\d)\d{5}(?!\d)'  # 5-digit ZIP with negative lookahead/behind
            ],
            "US_BANK_NUMBER": [
                r'\bRouting:?\s*(\d{9})\b',
                r'(?<!\d)\d{9}(?!\d)'  # 9 digits not part of larger number
            ],
            "ACCOUNT_NUMBER": [
                r'\bAcct:?\s*(\d{8,20})\b',
                r'\bAccount:?\s*(\d{8,20})\b'
            ],
            "US_DRIVER_LICENSE": [
                # Enhanced driver's license patterns
                r'\b[A-Z]\d{7,18}\b',           # Letter + 7-18 digits (CA, FL, etc.)
                r'(?<!\d)\d{8,16}(?!\d)',       # Pure digits 8-16 (many states)
                r'\b[A-Z]{2}\d{2,7}[A-Z]?\b',   # 2 letters + digits (AZ, CO, etc.)
                r'\b[A-Z]{3}\d{6}\b',           # 3 letters + 6 digits (ND)
                r'\bDL:?\s*([A-Z0-9]{4,18})\b', # Explicit DL prefix
                r'\bDriver\s*License:?\s*([A-Z0-9]{4,18})\b'
            ],
            "US_PASSPORT": [
                r'\b[A-Z]\d{8}\b',
                r'\bpassport\s+number:?\s*([A-Z0-9]{6,12})\b'
            ]
        }
    
    def detect_pii(self, text: str) -> dict:
        """
        Detect PII using regex-first approach with spaCy backup
        """
        try:
            # Phase 1: Apply regex patterns (high priority)
            regex_entities = self._detect_regex_entities(text)
            
            # Phase 2: Apply spaCy NER for remaining gaps
            spacy_entities = self._detect_spacy_entities(text, regex_entities)
            
            # Phase 3: Merge entities (regex has priority)
            all_entities = regex_entities + spacy_entities
            merged_entities = self._merge_entities(all_entities)
            
            # Phase 4: Apply redaction
            redacted_text = self._apply_redaction(text, merged_entities)
            
            return {
                "original_text": text,
                "redacted_text": redacted_text,
                "entities_found": len(merged_entities),
                "entities": merged_entities,
                "entity_summary": self._create_summary(merged_entities),
                "redaction_success": True
            }
            
        except Exception as e:
            return {
                "original_text": text,
                "redacted_text": text,
                "entities_found": 0,
                "entities": [],
                "entity_summary": {},
                "redaction_success": False,
                "error": str(e)
            }
    
    def _detect_regex_entities(self, text: str) -> List[Dict]:
        """Detect entities using regex patterns"""
        entities = []
        
        for entity_type, patterns in self.regex_patterns.items():
            for pattern in patterns:
                try:
                    for match in re.finditer(pattern, text, re.IGNORECASE):
                        # Handle patterns with capture groups
                        if match.groups():
                            start, end = match.span(1)
                            matched_text = match.group(1)
                        else:
                            start, end = match.span()
                            matched_text = match.group()
                        
                        # Additional validation for certain entity types
                        if self._validate_entity(entity_type, matched_text):
                            entities.append({
                                "start": start,
                                "end": end,
                                "entity_type": entity_type,
                                "text": matched_text,
                                "confidence": 0.95,
                                "source": "regex"
                            })
                except re.error as regex_error:
                    print(f"Regex error for {entity_type}: {regex_error}")
                    continue
        
        return entities
    
    def _validate_entity(self, entity_type: str, text: str) -> bool:
        """Additional validation for certain entity types"""
        # Avoid false positives for credit cards that are too short
        if entity_type == "CREDIT_CARD" and len(re.sub(r'\D', '', text)) < 13:
            return False
            
        # Validate phone numbers have correct digit count
        if entity_type == "PHONE_NUMBER":
            digits = re.sub(r'\D', '', text)
            return len(digits) == 10 or len(digits) == 11
            
        # Avoid very short driver license numbers
        if entity_type == "US_DRIVER_LICENSE" and len(text) < 4:
            return False
            
        return True
    
    def _detect_spacy_entities(self, text: str, existing_entities: List[Dict]) -> List[Dict]:
        """Detect entities using spaCy for gaps not covered by regex"""
        if not self.nlp:
            return []
            
        doc = self.nlp(text)
        entities = []
        
        for ent in doc.ents:
            entity_type = self._map_entity_type(ent.label_)
            if entity_type:
                # Check if this overlaps with existing regex entities
                overlaps = any(
                    self._entities_overlap(
                        {"start": ent.start_char, "end": ent.end_char},
                        existing
                    ) for existing in existing_entities
                )
                
                if not overlaps:
                    entities.append({
                        "start": ent.start_char,
                        "end": ent.end_char,
                        "entity_type": entity_type,
                        "text": ent.text,
                        "confidence": self._get_confidence(ent.label_),
                        "source": "spacy"
                    })
        
        return entities
    
    def _merge_entities(self, entities: List[Dict]) -> List[Dict]:
        """Merge entities with regex priority"""
        if not entities:
            return []
        
        # Sort by start position
        sorted_entities = sorted(entities, key=lambda x: x['start'])
        
        merged = []
        for entity in sorted_entities:
            overlaps = False
            for existing in merged:
                if self._entities_overlap(entity, existing):
                    overlaps = True
                    # Regex always wins over spaCy
                    if entity['source'] == 'regex' and existing['source'] == 'spacy':
                        merged.remove(existing)
                        merged.append(entity)
                    elif entity['source'] == existing['source'] and entity['confidence'] > existing['confidence']:
                        merged.remove(existing)
                        merged.append(entity)
                    break
            
            if not overlaps:
                merged.append(entity)
        
        return sorted(merged, key=lambda x: x['start'])
    
    def _entities_overlap(self, entity1: Dict, entity2: Dict) -> bool:
        """Check if two entities overlap"""
        return not (entity1['end'] <= entity2['start'] or entity1['start'] >= entity2['end'])
    
    def _apply_redaction(self, text: str, entities: List[Dict]) -> str:
        """Apply redaction to text"""
        if not entities:
            return text
        
        # Sort by start position in reverse order
        sorted_entities = sorted(entities, key=lambda x: x['start'], reverse=True)
        
        redacted_text = text
        for entity in sorted_entities:
            start, end = entity['start'], entity['end']
            replacement = f"<{entity['entity_type']}>"
            redacted_text = redacted_text[:start] + replacement + redacted_text[end:]
        
        return redacted_text
    
    def _map_entity_type(self, spacy_label: str) -> Optional[str]:
        """Map spaCy labels to PII entity types"""
        mapping = {
            "PERSON": "PERSON",
            "GPE": "LOCATION",
            "LOC": "LOCATION", 
            "ORG": "ORGANIZATION",
            "DATE": "DATE_TIME",
            "TIME": "DATE_TIME",
            "MONEY": "MONEY",
            "CARDINAL": "NUMBER"
        }
        return mapping.get(spacy_label)
    
    def _get_confidence(self, label: str) -> float:
        """Assign confidence scores"""
        return 0.85 if label in ["PERSON", "GPE", "LOC"] else 0.75
    
    def _create_summary(self, entities: List[Dict]) -> Dict:
        """Create summary of detected entities"""
        summary = {}
        for entity in entities:
            entity_type = entity['entity_type']
            summary[entity_type] = summary.get(entity_type, 0) + 1
        return summary

# Global detector instance
pii_detector = RegexFirstPIIDetector()

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
            # Handle image processing
            if not image.content_type.startswith("image/"):
                raise HTTPException(status_code=400, detail="Invalid file type. Please upload an image.")

            content = await image.read()
            pil_image = Image.open(io.BytesIO(content))
            
            # Create clean copy without EXIF data
            clean_image = Image.new(pil_image.mode, pil_image.size)
            clean_image.putdata(list(pil_image.getdata()))
        
            output = io.BytesIO()
            clean_image.save(output, format=pil_image.format, optimize=True)
            output.seek(0)
            
            width, height = pil_image.size
            img_base64 = base64.b64encode(output.read()).decode('utf-8')

            processing_data = {
                "original_filename": image.filename,
                "image_size": {"width": width, "height": height},
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
            # Handle text processing with regex-first approach
            pii_results = pii_detector.detect_pii(text_input.strip())
            
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

            message = f"Regex-first analysis completed! Found and redacted {pii_results['entities_found']} sensitive entities."
            if not pii_results["redaction_success"]:
                message += f" Warning: {pii_results.get('error', 'Unknown error occurred')}"

            return JSONResponse({
                "message": message,
                "data": processing_data,
                "redacted_text": pii_results["redacted_text"],
                "analysis_summary": {
                    "entities_by_type": pii_results["entity_summary"],
                    "detailed_entities": pii_results["entities"],
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
        regex_entities = list(pii_detector.regex_patterns.keys())
        spacy_entities = ["PERSON", "LOCATION", "ORGANIZATION", "DATE_TIME", "MONEY", "NUMBER"]
        
        return JSONResponse({
            "regex_entities": regex_entities,
            "spacy_entities": spacy_entities,
            "total_supported": len(regex_entities) + len(spacy_entities),
            "processing_pipeline": ["Regex Patterns (Priority)", "spaCy NER (Backup)", "Overlap Resolution"]
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not retrieve supported entities: {str(e)}")

@app.get("/api/model-status")
async def get_model_status():
    """Get status of detection models"""
    return JSONResponse({
        "spacy_status": "initialized" if pii_detector.nlp else "failed",
        "model_name": pii_detector.nlp.meta.get("name", "unknown") if pii_detector.nlp else "none",
        "regex_patterns": len(pii_detector.regex_patterns),
        "processing_engine": "Regex-First + spaCy NER"
    })