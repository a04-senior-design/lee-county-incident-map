"""
CountdownAnimation — proof-of-mechanism demo for MapAnimation.

Renders 10, 9, 8, ... 1, GO! as one PNG-per-frame overlay anchored to a
bounding box over Lee County, played back at a fixed interval. This exercises
the ImageFrame/PNG path end-to-end (numbered PNGs rasterized with Pillow,
then placed via folium.raster_layers.ImageOverlay) since that path — needed
for future rasterized density/heatmap overlays — is higher-risk than the
vector path and should be proven now rather than assumed.

How a future DBSCANClusterAnimation plugs into the same base class:
    class DBSCANClusterAnimation(MapAnimation):
        def __init__(self, snapshots: list[dict]):
            # snapshots = ~12 precomputed {eps, min_pts, geojson} per time window
            self._snapshots = snapshots
            super().__init__(frame_count=len(snapshots), interval_seconds=2.0, ...)

        def build_frame(self, index: int) -> Frame:
            snapshot = self._snapshots[index]
            # reuse run_clusters()'s GeoJSON output -> folium.GeoJson children
            children = [folium.GeoJson(snapshot["geojson"])]
            return VectorFrame(label=snapshot["window_label"], children=children)

Everything else (map setup, layer toggling, play/pause/scrub JS) is inherited
from MapAnimation unchanged.
"""

import os

from PIL import Image, ImageDraw, ImageFont

from .base import Frame, ImageFrame, MapAnimation

LEE_COUNTY_CENTER = (26.56, -81.87)

_FRAMES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "output", "countdown_frames")
_OUTPUT_HTML = os.path.join(os.path.dirname(__file__), "..", "..", "..", "output", "countdown_animation.html")

_IMAGE_SIZE = (400, 400)
_HALF_LAT = 0.05
_HALF_LON = 0.07

_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial Bold.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """Load a bold system font, falling back to Pillow's built-in font."""
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def _render_label_png(label: str, color: str, path: str) -> None:
    """Rasterize a single countdown label onto a transparent PNG."""
    image = Image.new("RGBA", _IMAGE_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = _load_font(size=int(_IMAGE_SIZE[1] * (0.4 if label == "GO!" else 0.55)))
    bbox = draw.textbbox((0, 0), label, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    position = ((_IMAGE_SIZE[0] - text_w) / 2 - bbox[0], (_IMAGE_SIZE[1] - text_h) / 2 - bbox[1])
    draw.text(position, label, font=font, fill=color)
    image.save(path)


class CountdownAnimation(MapAnimation):
    """10, 9, 8, ..., 1, GO! played back one PNG frame per interval."""

    LABELS = [str(n) for n in range(10, 0, -1)] + ["GO!"]

    def __init__(
        self,
        center: tuple = LEE_COUNTY_CENTER,
        zoom_start: int = 12,
        interval_seconds: float = 1.0,
        frames_dir: str = _FRAMES_DIR,
    ) -> None:
        super().__init__(
            frame_count=len(self.LABELS),
            interval_seconds=interval_seconds,
            center=center,
            zoom_start=zoom_start,
        )
        self._frames_dir = frames_dir
        os.makedirs(self._frames_dir, exist_ok=True)
        self._bounds = [
            [center[0] - _HALF_LAT, center[1] - _HALF_LON],
            [center[0] + _HALF_LAT, center[1] + _HALF_LON],
        ]

    def build_frame(self, index: int) -> Frame:
        label = self.LABELS[index]
        color = "#2A9D8F" if label == "GO!" else "#E63946"
        png_path = os.path.join(self._frames_dir, f"frame_{index:02d}.png")
        if not os.path.exists(png_path):
            _render_label_png(label, color, png_path)
        return ImageFrame(label=label, image=png_path, bounds=self._bounds)


def main() -> None:
    animation = CountdownAnimation()
    written = animation.to_html(_OUTPUT_HTML)
    print(f"Countdown animation saved to {os.path.abspath(written)}")


if __name__ == "__main__":
    main()
