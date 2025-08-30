import io
import cv2
import torch
from typing import List

import numpy as np
from PIL import Image


class Masking:

    def __init__(self, assume_format: str = "cxcywh"):
        self.assume_format = assume_format

    @staticmethod
    def scrub_exif_bytes(image_bytes: bytes) -> bytes:
        img = Image.open(io.BytesIO(image_bytes))

        data = list(img.getdata())
        clean = Image.new(img.mode, img.size)
        clean.putdata(data)

        buffer = io.BytesIO()
        clean.save(buffer, format=img.format)
        return buffer.getvalue()

    def pixelate_marked_regions(
            self,
            image_bgr: np.ndarray,
            boxes_norm: torch.Tensor,
            pixel_size: int = 12,
            use_sam_masks: bool = False
    ) -> bytes:
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        H, W = image_rgb.shape[:2]

        boxes_xyxy_px_t = self._boxes_norm_to_xyxy_px(boxes_norm, H, W, assume_format=self.assume_format)
        boxes_xyxy_px = boxes_xyxy_px_t.detach().cpu().numpy()

        if use_sam_masks:
            masks = self.get_enhanced_sam_masks(image_rgb, boxes_xyxy_px.tolist(), expand_masks=True)
        else:
            masks = self._rect_masks_from_boxes(image_rgb, boxes_xyxy_px)

        if not masks:
            # Encode original image if nothing to pixelate
            ok, buf = cv2.imencode(".jpg", image_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
            if not ok:
                raise ValueError("Could not encode image")
            return buf.tobytes()

        result_rgb = self._apply_smart_pixelate_effect(image_rgb, masks, pixel_size=pixel_size)
        result_bgr = cv2.cvtColor(result_rgb, cv2.COLOR_RGB2BGR)

        ok, buf = cv2.imencode(".jpg", result_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
        if not ok:
            raise ValueError("Could not encode pixelated result")

        return buf.tobytes()

    def _filter_large(self, boxes: torch.Tensor, logits: torch.Tensor, phrases: List[str]):
        """
        Remove boxes whose normalized area exceeds MAX_AREA_FRAC.
        Assumes boxes are normalized. Supports both "cxcywh" and "xyxy".
        """
        b = boxes.float()
        if self.assume_format == "cxcywh":
            # b = [cx,cy,w,h] in [0,1]
            area_frac = (b[:, 2] * b[:, 3]).clamp(min=0.0)
        elif self.assume_format == "xyxy":
            # b = [x1,y1,x2,y2] in [0,1]
            w = (b[:, 2] - b[:, 0]).clamp(min=0.0)
            h = (b[:, 3] - b[:, 1]).clamp(min=0.0)
            area_frac = (w * h)
        else:
            raise ValueError("Unknown box format for filtering")

        keep_mask = area_frac <= self.MAX_AREA_FRAC

        if keep_mask.ndim == 0:
            keep_mask = keep_mask.unsqueeze(0)
        keep_idx = keep_mask.nonzero(as_tuple=True)[0]

        b2 = b[keep_idx]
        l2 = logits[keep_idx] if logits.numel() else logits
        p2 = [phrases[i] for i in keep_idx.tolist()] if phrases else phrases
        return b2, l2, p2

    def _boxes_norm_to_xyxy_px(self, boxes_norm: torch.Tensor, H: int, W: int, assume_format="cxcywh") -> torch.Tensor:
        """
        Convert normalized boxes to pixel-space [x1,y1,x2,y2].
        """
        b = boxes_norm.detach().cpu().float()
        if assume_format == "xyxy":
            x1 = (b[:, 0] * W).clamp(0, W - 1)
            y1 = (b[:, 1] * H).clamp(0, H - 1)
            x2 = (b[:, 2] * W).clamp(0, W - 1)
            y2 = (b[:, 3] * H).clamp(0, H - 1)
        elif assume_format == "cxcywh":
            cx = b[:, 0] * W
            cy = b[:, 1] * H
            ww = b[:, 2] * W
            hh = b[:, 3] * H
            x1 = (cx - ww / 2).clamp(0, W - 1)
            y1 = (cy - hh / 2).clamp(0, H - 1)
            x2 = (cx + ww / 2).clamp(0, W - 1)
            y2 = (cy + hh / 2).clamp(0, H - 1)
        else:
            raise ValueError("Unknown assume_format")

        # ensure properly ordered ints
        x1i, y1i = x1.floor().to(torch.int64), y1.floor().to(torch.int64)
        x2i, y2i = x2.ceil().to(torch.int64), y2.ceil().to(torch.int64)
        x1i, x2i = torch.minimum(x1i, x2i), torch.maximum(x1i, x2i)
        y1i, y2i = torch.minimum(y1i, y2i), torch.maximum(y1i, y2i)
        return torch.stack([x1i, y1i, x2i, y2i], dim=1)

    def _rect_masks_from_boxes(self, image_rgb: np.ndarray, boxes_xyxy_px: np.ndarray) -> List[np.ndarray]:
        """
        Build boolean masks (H,W) from pixel-space boxes.
        """
        H, W = image_rgb.shape[:2]
        masks: List[np.ndarray] = []
        for x1, y1, x2, y2 in boxes_xyxy_px:
            x1, y1 = max(0, int(x1)), max(0, int(y1))
            x2, y2 = min(W, int(x2)), min(H, int(y2))
            if x2 <= x1 or y2 <= y1:
                continue
            m = np.zeros((H, W), dtype=bool)
            m[y1:y2, x1:x2] = True
            masks.append(m)
        return masks

    def _apply_smart_pixelate_effect(self, image_rgb: np.ndarray, masks: List[np.ndarray],
                                     pixel_size: int = 12) -> np.ndarray:
        """
        Your 'smart pixelation' with adaptive block sizes and mask-aware averaging.
        """
        if not masks:
            return image_rgb

        result = image_rgb.copy()

        for mask in masks:
            ys, xs = np.where(mask)
            if len(ys) == 0:
                continue

            min_y, max_y = ys.min(), ys.max()
            min_x, max_x = xs.min(), xs.max()

            region_w = max_x - min_x
            region_h = max_y - min_y
            adaptive_px = min(pixel_size, max(8, min(region_w // 5, region_h // 5)))

            # step through blocks
            for y in range(min_y, max_y, adaptive_px):
                for x in range(min_x, max_x, adaptive_px):
                    by2 = min(y + adaptive_px, max_y)
                    bx2 = min(x + adaptive_px, max_x)
                    block_mask = mask[y:by2, x:bx2]

                    if np.any(block_mask):
                        block_region = result[y:by2, x:bx2]
                        masked_pixels = block_region[block_mask]
                        if len(masked_pixels) > 0:
                            avg_color = np.mean(masked_pixels, axis=0)
                            block_region[block_mask] = avg_color

        return result

    def get_enhanced_sam_masks(self, image_rgb: np.ndarray, boxes_xyxy: List[List[int]], expand_masks: bool = True) -> \
            List[np.ndarray]:
        return self._rect_masks_from_boxes(image_rgb, np.array(boxes_xyxy, dtype=int))

