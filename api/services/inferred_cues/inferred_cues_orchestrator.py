import tempfile

import cv2
import numpy as np

from services.inferred_cues.grounding_dino_bounding_box import GroundingDinoBoundingBox
from services.inferred_cues.llm_geoguesser import LLMGeoGuesser
from services.models import GeoGuess


def dms_to_dd(dms, ref):
    """Convert degree, minute, second tuple to decimal degrees."""

    def _to_float(x):
        try:
            return float(x[0]) / float(x[1])  # handle rationals
        except Exception:
            return float(x)

    d, m, s = (_to_float(dms[0]), _to_float(dms[1]), _to_float(dms[2]))
    dd = d + m / 60.0 + s / 3600.0
    if ref in ['S', 'W']:
        dd = -dd
    return dd


class InferredCueOrchestrator:
    def __init__(self, agent: LLMGeoGuesser, model: GroundingDinoBoundingBox):
        self.agent = agent
        self.model = model

    # @staticmethod
    # def fetch_exif_data(image_bytes: bytes) -> ExifData:
    #     """Extract EXIF metadata + optional GPS lat/lon from image bytes.
    #     Returns exif_data with strictly string:string keys/values.
    #     """
    #     img = Image.open(BytesIO(image_bytes))
    #     exif_data = img._getexif()
    #     lat, lon = None, None
    #     parsed_exif = {}
    #
    #     if exif_data:
    #         parsed_exif = {
    #             str(ExifTags.TAGS.get(tag, tag)): str(value)
    #             for tag, value in exif_data.items()
    #         }
    #
    #         gps_info = exif_data.get(34853)  # 34853 is GPSInfo tag
    #         if gps_info:
    #             gps = {
    #                 str(ExifTags.GPSTAGS.get(k, k)): v
    #                 for k, v in gps_info.items()
    #             }
    #
    #             if "GPSLatitude" in gps and "GPSLongitude" in gps:
    #                 lat = dms_to_dd(gps["GPSLatitude"], gps.get("GPSLatitudeRef"))
    #                 lon = dms_to_dd(gps["GPSLongitude"], gps.get("GPSLongitudeRef"))
    #
    #     location = LocationCoord(lat=lat, lon=lon) if lat is not None and lon is not None else None
    #     return ExifData(exif_data={k: str(v) for k, v in parsed_exif.items()}, location=location)

    @staticmethod
    def resize_image(image_bytes: bytes, width: int, height: int) -> bytes:
        image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        resized = cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)

        success, buffer = cv2.imencode(".jpg", resized)
        if not success:
            raise ValueError("Could not encode image")

        return buffer.tobytes()

    def orchestrate(self, image_bytes: bytes) -> GeoGuess:
        resized_image = self.resize_image(image_bytes=image_bytes, width=720, height=540)

        llm_response = self.agent.with_backoff(lambda: self.agent.predict(resized_image))
        coordinates_guess = self.agent.guess_coordinates(llm_response)

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(resized_image)
            tmp.flush()
            serialized_bounding_box_data = self.model.mark_image(
                image_path=tmp.name,
                text_prompts=[f"{cue.location_cue}" for cue in coordinates_guess.predictions[0].location_cues]
            )

        return GeoGuess.from_bytes(
            resized_image_bytes=resized_image,
            prediction=coordinates_guess.predictions[0],
            bounding_box=serialized_bounding_box_data
        )
