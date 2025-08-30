import base64
from typing import Optional

import torch
from pydantic import BaseModel, Field


class Location(BaseModel):
    country: str
    city: str
    closest_likely_region: str = Field(
        description="Name of the region, street, institution. try to be specific or guess it"
    )

    string_query_for_openstreetmap: str = Field(description="a string query for openstreetmaps to search the location")


class LocationCues(BaseModel):
    priority: int
    location_cue: str
    reason: str


class LLMPrediction(BaseModel):
    confidence: float = Field(..., ge=0.0, le=1.0)
    detailed_location: Location
    location_cues: list[LocationCues]


class LLMPredictionsResponse(BaseModel):
    predictions: list[LLMPrediction]


class LocationCoord(BaseModel):
    lat: float = Field(description="Latitude coordinate", gt=-90, lt=90)
    lon: float = Field(description="Longitude coordinate", gt=-180, lt=180)


class LLMPredictionWithLatLong(LLMPrediction):
    coords: Optional[LocationCoord] = None


class LLMPredictionsResponseWithCoords(BaseModel):
    predictions: list[LLMPredictionWithLatLong]


class SerializedBoundingBoxCoord(BaseModel):
    image_bytes: str
    mapping: dict[str, dict[str, list[float] | float]]

    @classmethod
    def from_torch(
            cls,
            image_bytes: bytes,
            boxes: torch.Tensor,
            logits: torch.Tensor,
            phrases: list[str],
    ) -> "SerializedBoundingBoxCoord":
        """Create a serializable hashmap: phrase -> {box, logit}"""
        hashmap = {
            phrase: {
                "box": box.tolist(),
                "logit": float(logit),
            }
            for phrase, box, logit in zip(phrases, boxes.detach().cpu(), logits.detach().cpu())
        }

        return cls(
            image_bytes=base64.b64encode(image_bytes).decode("utf-8"),
            mapping=hashmap,
        )

    def to_torch(self) -> dict:
        """Reconstruct tensors and raw bytes from hashmap form."""
        phrases = list(self.mapping.keys())
        boxes = [self.mapping[p]["box"] for p in phrases]
        logits = [self.mapping[p]["logit"] for p in phrases]

        return {
            "image_bytes": base64.b64decode(self.image_bytes),
            "boxes": torch.tensor(boxes, dtype=torch.float32),
            "logits": torch.tensor(logits, dtype=torch.float32),
            "phrases": phrases,
        }


class GeoGuess(BaseModel):
    resized_image_bytes: str
    prediction: LLMPredictionWithLatLong
    bounding_box: SerializedBoundingBoxCoord

    @classmethod
    def from_bytes(
            cls,
            resized_image_bytes: bytes,
            prediction: LLMPredictionWithLatLong,
            bounding_box: SerializedBoundingBoxCoord,
    ) -> "GeoGuess":
        """Create serializable GeoGuess with base64 image encoding."""
        return cls(
            resized_image_bytes=base64.b64encode(resized_image_bytes).decode("utf-8"),
            prediction=prediction,
            bounding_box=bounding_box,
        )

    def to_bytes(self) -> dict:
        """Reconstruct raw bytes + components from serialized form."""
        return {
            "resized_image_bytes": base64.b64decode(self.resized_image_bytes),
            "prediction": self.prediction,
            "bounding_box": self.bounding_box,
        }


class MaskImage(BaseModel):
    resized_image_bytes: str
    mapping: dict[str, dict[str, list[float] | float]]

    def to_torch(self) -> dict:
        """Reconstruct tensors and raw bytes from hashmap form."""
        phrases = list(self.mapping.keys())
        boxes = [self.mapping[p]["box"] for p in phrases]
        logits = [self.mapping[p]["logit"] for p in phrases]

        return {
            "resized_image_bytes": base64.b64decode(self.resized_image_bytes),
            "boxes": torch.tensor(boxes, dtype=torch.float32),
            "logits": torch.tensor(logits, dtype=torch.float32),
            "phrases": phrases,
        }
