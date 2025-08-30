import re
import spacy
from typing import List, Dict, Optional

class RegexFirstPIIDetector:
    """Regex-first PII detection with spaCy backup"""
    ENTITY_PRIORITY = {
        "US_PASSPORT": 3,      # higher than driver license
        "US_DRIVER_LICENSE": 2
    }

    def __init__(self):
        self.nlp = None
        self.initialize_spacy()
        self.regex_patterns = self._setup_regex_patterns()

    def initialize_spacy(self):
        try:
            try:
                self.nlp = spacy.load("en_core_web_trf")
            except IOError:
                self.nlp = spacy.load("en_core_web_sm")
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
                r'\b\d{1,6}\s+[A-Za-z0-9\s\.-]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Circle|Cir|Way|Terrace|Ter|Place|Pl|Plaza|Pkwy|Parkway)\s*,\s*[A-Za-z\s]+,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?\b',
                r'\b\d{1,6}\s+[A-Za-z0-9\s\.-]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Circle|Cir|Way|Terrace|Ter|Place|Pl|Plaza|Pkwy|Parkway)(?:\s*,?\s*(?:Apt|Apartment|Suite|Ste|Unit|#)\s*[A-Za-z0-9-]+)?\b',
                r'\bP\.?O\.?\s*Box\s+\d+\b',
                r'\b[A-Za-z\s]{2,30},\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?\b'
            ],
            "ZIP_CODE": [
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
                r'\b[A-Z]\d{7,18}\b',
                r'(?<!\d)\d{8,16}(?!\d)'
                r'\b[A-Z]{2}\d{2,7}[A-Z]?\b',
                r'\b[A-Z]{3}\d{6}\b',
                r'\bDL:?\s*([A-Z0-9]{4,18})\b',
                r'\bDriver\s*License:?\s*([A-Z0-9]{4,18})\b'
            ],
            "US_PASSPORT": [
                r'\b[A-Z]\d{8}\b',
                r'\bpassport\s+number:?\s*([A-Z0-9]{6,12})\b'
            ]
        }

    def detect_pii(self, text: str) -> dict:
        """Detect PII using regex + spaCy"""
        regex_entities = self._detect_regex_entities(text)
        spacy_entities = self._detect_spacy_entities(text, regex_entities)
        all_entities = self._merge_entities(regex_entities + spacy_entities)
        redacted_text = self._apply_redaction(text, all_entities)

        return {
            "original_text": text,
            "redacted_text": redacted_text,
            "entities_found": len(all_entities),
            "all_entities": all_entities,
            "entity_summary": self._create_summary(all_entities),
            "redaction_success": True
        }

    def process_text(self, text: str) -> dict:
        """Return a full JSON-ready response for FastAPI"""
        results = self.detect_pii(text.strip())
        return {
            "message": f"Text analysis completed! Found and redacted {results['entities_found']} sensitive entities.",
            "data": {
                "file_size": len(text.encode("utf-8")),
                "format": "text",
                "processing_status": "completed" if results["redaction_success"] else "failed",
                "input_type": "text",
                "original_length": len(text),
                "redacted_length": len(results["redacted_text"]),
                "entities_detected": results["entity_summary"],
                "total_entities_found": results["entities_found"]
            },
            "redacted_text": results["redacted_text"],
            "analysis_summary": {
                "entities_by_type": results["entity_summary"],
                "detailed_entities": results["all_entities"],
                "redaction_success": results["redaction_success"]
            }
        }

    def _detect_regex_entities(self, text: str) -> List[Dict]:
        entities = []
        for entity_type, patterns in self.regex_patterns.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    start, end = match.span(1) if match.groups() else match.span()
                    matched_text = match.group(1) if match.groups() else match.group()
                    entities.append({
                        "start": start,
                        "end": end,
                        "entity_type": entity_type,
                        "text": matched_text,
                        "confidence": 0.95,
                        "source": "regex"
                    })
        return entities

    def _detect_spacy_entities(self, text: str, existing_entities: List[Dict]) -> List[Dict]:
        if not self.nlp:
            return []
        doc = self.nlp(text)
        entities = []
        for ent in doc.ents:
            entity_type = self._map_entity_type(ent.label_)
            if entity_type and not any(self._entities_overlap({"start": ent.start_char, "end": ent.end_char}, e) for e in existing_entities):
                entities.append({
                    "start": ent.start_char,
                    "end": ent.end_char,
                    "entity_type": entity_type,
                    "text": ent.text,
                    "confidence": 0.85,
                    "source": "spacy"
                })
        return entities

    def _merge_entities(self, entities: List[Dict]) -> List[Dict]:
        # Sort by start position and priority (higher priority first)
        sorted_entities = sorted(
            entities,
            key=lambda x: (x['start'], -self.ENTITY_PRIORITY.get(x['entity_type'], 0))
        )

        merged = []
        for entity in sorted_entities:
            to_replace = None
            for idx, existing in enumerate(merged):
                if self._entities_overlap(entity, existing):
                    # Keep the higher-priority entity
                    if self.ENTITY_PRIORITY.get(entity['entity_type'], 0) > self.ENTITY_PRIORITY.get(existing['entity_type'], 0):
                        to_replace = idx
                    break
            if to_replace is not None:
                merged[to_replace] = entity
            elif all(not self._entities_overlap(entity, e) for e in merged):
                merged.append(entity)

        return merged

    def _entities_overlap(self, e1: Dict, e2: Dict) -> bool:
        return not (e1['end'] <= e2['start'] or e1['start'] >= e2['end'])

    def _apply_redaction(self, text: str, entities: List[Dict]) -> str:
        sorted_entities = sorted(entities, key=lambda x: x['start'], reverse=True)
        for entity in sorted_entities:
            text = text[:entity['start']] + f"<{entity['entity_type']}>" + text[entity['end']:]
        return text

    def _map_entity_type(self, label: str) -> Optional[str]:
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
        return mapping.get(label)

    def _create_summary(self, entities: List[Dict]) -> Dict:
        summary = {}
        for entity in entities:
            summary[entity['entity_type']] = summary.get(entity['entity_type'], 0) + 1
        return summary

# global instance
pii_detector = RegexFirstPIIDetector()
