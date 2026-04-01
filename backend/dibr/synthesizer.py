"""
DIBR (Depth Image Based Rendering) 视角合成模块
"""

import numpy as np
import cv2
from typing import Tuple, Optional


class DIBRSynthesizer:
    def synthesize(
        self,
        image: np.ndarray,
        depth: np.ndarray,
        shift: float = 0.05,
        fill_holes: bool = True,
    ) -> np.ndarray:
        H, W = image.shape[:2]
        d_min, d_max = depth.min(), depth.max()
        if d_max - d_min < 1e-6:
            return image.copy()
        depth_norm = (depth - d_min) / (d_max - d_min)

        disparity = shift * W * depth_norm
        x_src = np.arange(W, dtype=np.float32)
        y_src = np.arange(H, dtype=np.float32)
        xx, yy = np.meshgrid(x_src, y_src)

        map_x = (xx - disparity).astype(np.float32)
        map_y = yy.astype(np.float32)

        synthesized = cv2.remap(
            image, map_x, map_y,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )

        if fill_holes:
            synthesized = self._fill_holes(synthesized, map_x, W)

        return synthesized

    def generate_stereo_pair(
        self, image: np.ndarray, depth: np.ndarray, shift: float = 0.05
    ) -> Tuple[np.ndarray, np.ndarray]:
        left = self.synthesize(image, depth, shift=-abs(shift))
        right = self.synthesize(image, depth, shift=abs(shift))
        return left, right

    def generate_anaglyph(
        self, image: np.ndarray, depth: np.ndarray, shift: float = 0.05
    ) -> np.ndarray:
        left, right = self.generate_stereo_pair(image, depth, shift)
        anaglyph = np.zeros_like(image)
        anaglyph[:, :, 0] = left[:, :, 0]
        anaglyph[:, :, 1] = right[:, :, 1]
        anaglyph[:, :, 2] = right[:, :, 2]
        return anaglyph

    def generate_side_by_side(
        self, image: np.ndarray, depth: np.ndarray, shift: float = 0.05
    ) -> np.ndarray:
        left, right = self.generate_stereo_pair(image, depth, shift)
        return np.concatenate([left, right], axis=1)

    def generate_multi_view(
        self, image: np.ndarray, depth: np.ndarray,
        num_views: int = 7, max_shift: float = 0.08
    ) -> list:
        shifts = np.linspace(-max_shift, max_shift, num_views)
        views = []
        for s in shifts:
            if abs(s) < 1e-4:
                views.append(image.copy())
            else:
                views.append(self.synthesize(image, depth, shift=float(s)))
        return views

    @staticmethod
    def _fill_holes(image: np.ndarray, map_x: np.ndarray, width: int) -> np.ndarray:
        mask = ((map_x < 0) | (map_x >= width)).astype(np.uint8) * 255
        if mask.sum() == 0:
            return image
        return cv2.inpaint(image, mask, 3, cv2.INPAINT_TELEA)


_synthesizer: Optional[DIBRSynthesizer] = None


def get_synthesizer() -> DIBRSynthesizer:
    global _synthesizer
    if _synthesizer is None:
        _synthesizer = DIBRSynthesizer()
    return _synthesizer
