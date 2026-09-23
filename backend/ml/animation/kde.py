"""
KDEAnimation — plays back precomputed KDE density-heatmap PNG overlays, one
bandwidth per frame, using the same MapAnimation mechanics as
CountdownAnimation/DBSCANClusterAnimation.

The PNGs (backend/ml/animation/png-images/density_overlay_bw*.png) are
pre-rendered RGBA rasters, each a full-extent KDE density surface for Lee
County at a different bandwidth, so this reuses the ImageFrame path (see
CountdownAnimation) rather than VectorFrame: build_frame() just anchors each
PNG to the same fixed bounding box and lets MapAnimation handle
play/pause/scrub across frames.
"""

import os

from .base import Frame, ImageFrame, MapAnimation

LEE_COUNTY_CENTER = (26.56, -81.87)

# [[south, west], [north, east]] -- shared extent all density_overlay_bw*.png were rendered against
BOUNDS = [[26.31513471258987, -82.22274415207067], [26.75195627738442, -81.56529668538192]]

# Fine to coarse, matches the density_overlay_bw{n}.png filenames
BANDWIDTHS = [600, 1200, 2400, 4800] # tmp

PNG_DIR = os.path.join(os.path.dirname(__file__), "png-images")
_OUTPUT_HTML = os.path.join(os.path.dirname(__file__), "..", "..", "..", "output", "kde_density_animation.html")


def list_frames() -> list:
    """Frame metadata (label, bandwidth, PNG filename under PNG_DIR) for every
    bandwidth, fine to coarse -- used by both KDEAnimation and the
    /api/animation/kde Flask endpoint so the frame list is defined once."""
    return [
        {"label": f"Bandwidth {bw}", "bandwidth": bw, "filename": f"density_overlay_bw{bw}.png"}
        for bw in BANDWIDTHS
    ]


class KDEAnimation(MapAnimation):
    """Plays back a sequence of precomputed KDE density-overlay PNGs, one per bandwidth, fine to coarse."""

    def __init__(
        self,
        png_dir: str = PNG_DIR,
        bandwidths: list = BANDWIDTHS,
        center: tuple = LEE_COUNTY_CENTER,
        zoom_start: int = 11,
        interval_seconds: float = 2.0,
    ) -> None:
        self._png_dir = png_dir
        self._bandwidths = list(bandwidths)
        super().__init__(
            frame_count=len(self._bandwidths),
            interval_seconds=interval_seconds,
            center=center,
            zoom_start=zoom_start,
        )

    def build_frame(self, index: int) -> Frame:
        bandwidth = self._bandwidths[index]
        png_path = os.path.join(self._png_dir, f"density_overlay_bw{bandwidth}.png")
        return ImageFrame(label=f"Bandwidth {bandwidth}", image=png_path, bounds=BOUNDS)


def main() -> None:
    animation = KDEAnimation()
    written = animation.to_html(_OUTPUT_HTML)
    print(f"KDE density animation saved to {os.path.abspath(written)}")


if __name__ == "__main__":
    main()
