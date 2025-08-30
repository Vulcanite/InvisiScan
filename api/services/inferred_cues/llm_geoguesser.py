import requests
from pydantic_ai import Agent, BinaryContent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.settings import ModelSettings
from typing import Callable, Any
from services.models import LLMPredictionsResponse, LocationCoord, LLMPredictionsResponseWithCoords, \
    LLMPredictionWithLatLong
import random
import time

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class LLMGeoGuesser:
    SYSTEM_PROMPT = """
    You are "GeoPrivacy-LLM", an assistant that predicts possible geographic locations from visual 
    and textual cues in an image.

    GOAL
    - Given 
    - Each hypothesis should include:
      - A numeric confidence score between 0.0 and 1.0.
      - location (place_label, country, region, city — null if unknown).
      - A list of location_cues, each with a priority (1..N, where 1 means critical, and N is minor) which can be 
        removed to obscure the location and a short reason.

    CONSTRAINTS
    - Confidence must be between 0.0 and 1.0.
    - Return multiple hypotheses when possible.
    - Do not return generic regions like 'Western Europe', 'East Asia', 'Unknown', 'N/A', 
      or vague phrases like 'university campus', 'public park', 'office building'.
    - Instead, always pick the **most specific named place** you can reasonably infer 
      (e.g., 'Sri Mariamman Temple' instead of 'likely a temple').
    - If multiple specific institutions or landmarks fit, pick the **single best guess** 
      with reasoning, not a category.
    - Be bold: prefer a concrete proper noun (e.g., 'Botanic Gardens', 'Bukit Timah Nature Reserve') 
      over a generic type of place.

    EXAMPLES
    - When identifying locations or landmarks:
        - ❌ Do not return vague terms like “likely a mountain range”.
        - ✅ Instead, return the specific name: “Himalayas” (or “Mount Everest” if the peak is clearly visible).

    - When identifying buildings or structures:
        - ❌ Do not return generic categories like “likely a temple”.
        - ✅ Instead, return the specific named entity: “Sri Mariamman Temple”.
    
    - When identifying location cues:
        - Focus on concrete, nameable items. keep the name as short as possible, to make object detection easier.
        - ❌ Don’t return vague descriptions like “street furniture” or “transportation infrastructure” 
             or "Architectural Style" or "Lush tropical vegetation"
        - ✅ Instead, return the specific element: “red post box,” "No Smoking Sign", “yellow fire hydrant,” 
             “double-decker bus,” "White tiled pillar," "yellow ceiling, " "Fern"
        
    
    - When generating a query string:
        - Only include core geographic identifiers (city, region, country).
        - ❌ Do not include filler descriptors such as residential, street, house, road, alley, building.
        - ✅ For example:
                Input: “residential street Székesfehérvár Hungary”
                Output: “Székesfehérvár Hungary”

    This ensures compatibility with APIs like OpenStreetMap.
    """

    def __init__(self, google_model: GoogleModel, settings: ModelSettings):
        self.google_model = google_model
        self.agent = Agent(google_model, output_type=LLMPredictionsResponse, model_settings=settings,
                           system_prompt=self.SYSTEM_PROMPT)

    @staticmethod
    def is_retryable_error(exc: Exception) -> bool:
        """Best-effort check for transient HTTP errors across common client libs."""
        msg = str(exc).lower()
        for code in RETRYABLE_STATUS:
            if f" {code} " in msg or f"{code}:" in msg or f"{code}," in msg:
                return True
        transient_markers = [
            "timeout", "timed out", "temporarily unavailable",
            "connection reset", "connection aborted",
            "service unavailable", "rate limit", "rate-limited",
            "too many requests", "backoff", "retry later"
        ]
        return any(tok in msg for tok in transient_markers)

    @staticmethod
    def with_backoff(
            fn: Callable[[], Any],
            *,
            max_retries: int = 6,
            base_sleep: float = 0.8,  # seconds
            max_sleep: float = 20.0,  # cap
            jitter: float = 0.25  # +/-25% jitter
    ) -> Any:
        attempt = 0
        while True:
            try:
                return fn()
            except Exception as exc:
                attempt += 1
                if attempt > max_retries or not LLMGeoGuesser.is_retryable_error(exc):
                    # Non-retryable or out of retries: bubble up
                    raise
                # exponential backoff with decorrelated jitter
                backoff = min(max_sleep, base_sleep * (2 ** (attempt - 1)))
                # +/- jitter%
                jitter_factor = 1 + random.uniform(-jitter, jitter)
                sleep_s = max(0.1, backoff * jitter_factor)
                print(f"[retry {attempt}/{max_retries}] transient error: {exc}\n"
                      f"Sleeping {sleep_s:.2f}s before retrying...")
                time.sleep(sleep_s)

    def predict(self, image_bytes: bytes) -> LLMPredictionsResponse:
        result = self.agent.run_sync([
            "guess where is this image was taken (try to be as specific as possible), and give specific reasoning",
            BinaryContent(data=image_bytes, media_type='image/png')]
        )
        return result.output

    @staticmethod
    def __openstreet_maps(place_name) -> LocationCoord:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": place_name,
            "format": "json",
            "limit": 1
        }
        headers = {"User-Agent": "GeoPrivacy-LLM/1.0"}  # OSM requires identifying header
        response = requests.get(url, params=params, headers=headers)

        if response.status_code == 200:
            data = response.json()
            print(data)
            if data:
                lat = float(data[0]["lat"])
                lon = float(data[0]["lon"])
                return LocationCoord(lat=lat, lon=lon)
        return None

    def guess_coordinates(self, llm_response: LLMPredictionsResponse):
        llm_response_with_coords = LLMPredictionsResponseWithCoords(predictions=[])
        prediction = llm_response.predictions[0]
        coords = self.__openstreet_maps(prediction.detailed_location.string_query_for_openstreetmap)
        llm_response_with_coords.predictions.append(
            LLMPredictionWithLatLong(
                confidence=prediction.confidence,
                detailed_location=prediction.detailed_location,
                location_cues=prediction.location_cues,
                coords=coords
            )
        )
        return llm_response_with_coords
