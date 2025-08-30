import os

import numpy as np
import torch
from groundingdino.util.inference import load_model, load_image, predict, annotate
import cv2

from services.models import SerializedBoundingBoxCoord


class GroundingDinoBoundingBox:
    BASE_PATH = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    CONFIG_PATH = os.path.join(
        BASE_PATH,
        "GroundingDINO",
        "groundingdino",
        "config",
        "GroundingDINO_SwinT_OGC.py"
    )
    WEIGHTS_PATH = os.path.join(
        BASE_PATH,
        "GroundingDINO",
        "weights",
        "groundingdino_swint_ogc.pth"
    )

    BOX_THRESHOLD = 0.37
    TEXT_THRESHOLD = 0.25
    MAX_AREA_FRAC = 0.25

    def __init__(self):
        self.model = load_model(self.CONFIG_PATH, self.WEIGHTS_PATH)

    def _filter_large(self, boxes: torch.Tensor, logits: torch.Tensor, phrases: list[str]):
        """
        Filters out boxes with area fraction > MAX_AREA_FRAC.
        Assumes boxes are in (cx, cy, w, h) normalized OR equivalent where boxes[:,2]*boxes[:,3] = area_frac.
        """
        if boxes.numel() == 0:
            return boxes, logits, []
        area_frac = boxes[:, 2] * boxes[:, 3]
        keep_mask = (area_frac <= self.MAX_AREA_FRAC)
        boxes = boxes[keep_mask]
        logits = logits[keep_mask]
        phrases = [p for p, k in zip(phrases, keep_mask.tolist()) if k]
        return boxes, logits, phrases

    @staticmethod
    def _to_xyxy_pixels(boxes_norm: torch.Tensor, H: int, W: int) -> np.ndarray:
        """
        GroundingDINO typically returns (cx, cy, w, h) in normalized coords.
        Convert to (x1,y1,x2,y2) in *pixel* coords and clamp to image bounds.
        If you're actually getting (x1,y1,x2,y2) normalized, set is_xyxy_norm=True.
        """
        b = boxes_norm.clone()
        # convert cxcywh -> xyxy (normalized)
        cx, cy, w, h = b[:, 0], b[:, 1], b[:, 2], b[:, 3]
        x1 = cx - w / 2.0
        y1 = cy - h / 2.0
        x2 = cx + w / 2.0
        y2 = cy + h / 2.0

        # clamp to [0,1]
        x1 = x1.clamp(0.0, 1.0)
        y1 = y1.clamp(0.0, 1.0)
        x2 = x2.clamp(0.0, 1.0)
        y2 = y2.clamp(0.0, 1.0)

        # scale to pixels
        x1 = (x1 * W).round().long()
        y1 = (y1 * H).round().long()
        x2 = (x2 * W).round().long()
        y2 = (y2 * H).round().long()

        # ensure min<=max and stay in-bounds
        x1 = torch.clamp(torch.minimum(x1, x2), 0, W - 1)
        y1 = torch.clamp(torch.minimum(y1, y2), 0, H - 1)
        x2 = torch.clamp(torch.maximum(x1, x2), 0, W - 1)
        y2 = torch.clamp(torch.maximum(y1, y2), 0, H - 1)

        return torch.stack([x1, y1, x2, y2], dim=1).cpu().numpy()

    def annotate_inbounds(
            self,
            image_bgr: np.ndarray,
            boxes_norm: torch.Tensor,
            logits: torch.Tensor,
            phrases: list[str],
            font=cv2.FONT_HERSHEY_SIMPLEX,
            font_scale=0.5,
            thickness=1,
    ):
        """
        Draws boxes and labels while guaranteeing the text stays inside the image
        (and inside the box if needed).
        """
        out = image_bgr.copy()
        H, W = out.shape[:2]

        if boxes_norm.numel() == 0:
            return out

        xyxy = self._to_xyxy_pixels(boxes_norm, H, W)

        for (x1, y1, x2, y2), score, phrase in zip(xyxy, logits.cpu().tolist(), phrases):
            # draw box
            cv2.rectangle(out, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)

            label = f"{phrase} {float(score):.2f}"
            (tw, th), baseline = cv2.getTextSize(label, font, font_scale, thickness)
            pad = 4

            # preferred label position: above the box
            rect_x1, rect_y1 = int(x1), int(y1) - th - baseline - 2 * pad
            rect_x2, rect_y2 = int(x1) + tw + 2 * pad, int(y1) - 2

            # if above goes out of image, try inside-top of the box
            if rect_y1 < 0:
                rect_y1 = int(y1) + 2
                rect_y2 = rect_y1 + th + baseline + 2 * pad

            # clamp horizontally into the image
            shift_x = 0
            if rect_x2 > W:
                shift_x = W - rect_x2
            if rect_x1 + shift_x < 0:
                shift_x = -rect_x1  # shove to left edge if still off
            rect_x1 += shift_x
            rect_x2 += shift_x

            # final clamp vertically into the image if still overflowing
            if rect_y2 > H:
                # place at bottom inside the box
                rect_y2 = int(y2) - 2
                rect_y1 = rect_y2 - (th + baseline + 2 * pad)
                if rect_y1 < 0:
                    rect_y1 = 0

            # draw filled background
            cv2.rectangle(out, (rect_x1, rect_y1), (rect_x2, rect_y2), (0, 255, 0), -1)

            # text origin (baseline)
            text_x = rect_x1 + pad
            text_y = rect_y2 - pad - baseline

            # draw text (dark text on green bg)
            cv2.putText(out, label, (text_x, text_y), font, font_scale, (0, 0, 0), thickness, cv2.LINE_AA)

        return out

    def mark_image(self, image_path: str, text_prompts: list[str]) -> SerializedBoundingBoxCoord:
        image_source, image = load_image(image_path)

        per_prompt_boxes = []
        per_prompt_logits = []
        all_phrases: list[str] = []

        for txt in text_prompts:
            boxes, logits, phrases = predict(
                model=self.model,
                image=image,
                caption=txt,
                box_threshold=self.BOX_THRESHOLD,
                text_threshold=self.TEXT_THRESHOLD,
                device=torch.device("mps" if torch.backends.mps.is_available() else "cpu")
            )

            # Normalize types to tensors
            if not isinstance(boxes, torch.Tensor):
                boxes = torch.tensor(boxes)
            if not isinstance(logits, torch.Tensor):
                logits = torch.tensor(logits)

            # Filter out overly large boxes
            boxes, logits, phrases = self._filter_large(boxes, logits, phrases)

            # Skip if nothing for this prompt
            if boxes.numel() == 0:
                print(phrases, txt)
                continue

            per_prompt_boxes.append(boxes[0].unsqueeze(0))
            per_prompt_logits.append(logits[0].unsqueeze(0))
            all_phrases.append(txt)

        # Concatenate across prompts
        if len(per_prompt_boxes) == 0:
            # No detections at all: return original image with empty tensors
            ok, buffer = cv2.imencode(".jpg", image_source)
            if not ok:
                raise ValueError("Could not encode image")
            return SerializedBoundingBoxCoord.from_torch(
                image_bytes=buffer.tobytes(),
                boxes=torch.empty((0, 4), dtype=torch.float32),
                logits=torch.empty((0,), dtype=torch.float32),
                phrases=[],
            )

        all_boxes = torch.cat(per_prompt_boxes, dim=0)
        all_logits = torch.cat(per_prompt_logits, dim=0)

        image_bgr = cv2.cvtColor(image_source, cv2.COLOR_RGB2BGR)
        annotated_frame = self.annotate_inbounds(
            image_bgr=image_bgr,
            boxes_norm=all_boxes,
            logits=all_logits,
            phrases=all_phrases,
        )
        ok, buffer = cv2.imencode(".jpg", annotated_frame)
        if not ok:
            raise ValueError("Could not encode image")

        return SerializedBoundingBoxCoord.from_torch(
            image_bytes=buffer.tobytes(),
            boxes=all_boxes,
            logits=all_logits,
            phrases=all_phrases,
        )
