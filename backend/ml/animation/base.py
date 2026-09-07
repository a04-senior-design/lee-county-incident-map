"""
Generic map-animation mechanics: an ordered sequence of frames played over a
Leaflet/folium map with play/pause/scrub controls, saved as a standalone HTML
file.

Two frame content types are supported from day one:
  - VectorFrame — wraps folium vector children (Marker, GeoJson, CircleMarker, ...)
  - ImageFrame  — wraps a folium.raster_layers.ImageOverlay pointing at a PNG
                  anchored to a lat/lon bounding box

`MapAnimation` owns everything generic (map setup, layer registration, the
JS play/pause/scrub control). Subclasses only implement `build_frame()` to
say how a single frame (of either type) is produced — see
backend/ml/animation/countdown.py for a worked example, and its module
docstring for how a future DBSCANClusterAnimation would plug in.
"""

import json
import os
from abc import ABC, abstractmethod
from typing import List, Sequence, Tuple

import folium
import folium.raster_layers
from branca.element import MacroElement
from jinja2 import Template


class Frame(ABC):
    """A single frame's content. Knows only how to build its own map layer."""

    def __init__(self, label: str) -> None:
        self.label = label

    @abstractmethod
    def build_layer(self, index: int) -> folium.FeatureGroup:
        """Build and return a folium.FeatureGroup containing this frame's content."""


class VectorFrame(Frame):
    """Frame built from vector/GeoJSON-style folium children.

    Use this for anything expressible as folium Markers/GeoJson/CircleMarker/etc.
    — e.g. a future DBSCANClusterAnimation frame made of cluster polygons.
    """

    def __init__(self, label: str, children: Sequence[folium.map.Layer]) -> None:
        super().__init__(label)
        self.children = list(children)

    def build_layer(self, index: int) -> folium.FeatureGroup:
        layer = folium.FeatureGroup(name=f"frame-{index}-{self.label}")
        for child in self.children:
            child.add_to(layer)
        return layer


class ImageFrame(Frame):
    """Frame backed by a pre-rendered PNG anchored to a bounding box.

    Use this for raster overlays that aren't produced as vector data — e.g. a
    rasterized KDE/heatmap density surface rendered outside Folium.
    """

    def __init__(
        self,
        label: str,
        image: str,
        bounds: List[List[float]],
        opacity: float = 1.0,
    ) -> None:
        super().__init__(label)
        self.image = image
        self.bounds = bounds
        self.opacity = opacity

    def build_layer(self, index: int) -> folium.FeatureGroup:
        layer = folium.FeatureGroup(name=f"frame-{index}-{self.label}")
        folium.raster_layers.ImageOverlay(
            image=self.image,
            bounds=self.bounds,
            opacity=self.opacity,
        ).add_to(layer)
        return layer


class _AnimationControl(MacroElement):
    """Injects the play/pause/scrub JS control that toggles frame layers on the map.

    Not part of the public API — MapAnimation.render() attaches one of these
    to the map automatically.
    """

    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function() {
            var map = {{ this.map_name }};
            var layers = [{% for name in this.layer_names %}{{ name }}{% if not loop.last %}, {% endif %}{% endfor %}];
            var labels = {{ this.labels_json }};
            var intervalMs = {{ this.interval_ms }};
            var current = 0;
            var timer = null;

            var panel = document.createElement('div');
            panel.id = '{{ this.get_name() }}';
            panel.style.cssText = 'position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);' +
                'z-index: 9999; background: rgba(255,255,255,0.95); padding: 10px 16px; border-radius: 8px;' +
                'box-shadow: 0 2px 8px rgba(0,0,0,0.35); font-family: sans-serif; text-align: center; min-width: 260px;';
            panel.innerHTML =
                '<button id="{{ this.get_name() }}-play" style="width: 2.2em; margin-right: 8px;">&#9654;</button>' +
                '<input id="{{ this.get_name() }}-scrub" type="range" min="0" max="' + (layers.length - 1) + '" value="0" style="width: 200px; vertical-align: middle;">' +
                '<div id="{{ this.get_name() }}-label" style="margin-top: 4px; font-size: 1.1em; font-weight: 600;"></div>';
            document.body.appendChild(panel);

            var playBtn = document.getElementById('{{ this.get_name() }}-play');
            var scrub = document.getElementById('{{ this.get_name() }}-scrub');
            var labelEl = document.getElementById('{{ this.get_name() }}-label');

            function showFrame(i) {
                layers.forEach(function(layer) { if (map.hasLayer(layer)) map.removeLayer(layer); });
                map.addLayer(layers[i]);
                scrub.value = i;
                labelEl.textContent = labels[i];
                current = i;
            }

            function pause() {
                if (timer) { clearInterval(timer); timer = null; }
                playBtn.innerHTML = '&#9654;';
            }

            function play() {
                if (timer) return;
                playBtn.innerHTML = '&#10074;&#10074;';
                timer = setInterval(function() {
                    showFrame((current + 1) % layers.length);
                }, intervalMs);
            }

            playBtn.addEventListener('click', function() { timer ? pause() : play(); });
            scrub.addEventListener('input', function() { pause(); showFrame(parseInt(scrub.value, 10)); });

            showFrame(0);
        })();
        {% endmacro %}
        """
    )

    def __init__(self, map_name: str, layer_names: List[str], labels: List[str], interval_ms: int) -> None:
        super().__init__()
        self._name = "AnimationControl"
        self.map_name = map_name
        self.layer_names = layer_names
        self.labels_json = json.dumps(labels)
        self.interval_ms = interval_ms


class MapAnimation(ABC):
    """
    Abstract base for map-based frame animations.

    Owns the generic mechanics shared by every animation: an ordered sequence
    of frames, a fixed interval between frames, and the play/pause/scrub
    controls rendered into a self-contained HTML file. Subclasses only need
    to implement `build_frame()` to say how a single frame's content is
    produced (see CountdownAnimation); `render()` / `to_html()` are reused
    unchanged by every subclass, including a future DBSCANClusterAnimation
    that hands back ~12 precomputed cluster-polygon frames instead of
    countdown numbers.
    """

    def __init__(
        self,
        frame_count: int,
        interval_seconds: float = 1.0,
        center: Tuple[float, float] = (26.56, -81.87),
        zoom_start: int = 11,
    ) -> None:
        if frame_count < 1:
            raise ValueError("frame_count must be >= 1")
        self.frame_count = frame_count
        self.interval_seconds = interval_seconds
        self.center = center
        self.zoom_start = zoom_start

    @abstractmethod
    def build_frame(self, index: int) -> Frame:
        """Produce the Frame for the given 0-based frame index (0 <= index < frame_count)."""

    def render(self) -> folium.Map:
        """Build the folium.Map containing every frame layer plus the animation control."""
        m = folium.Map(location=list(self.center), zoom_start=self.zoom_start)

        layer_names = []
        labels = []
        for index in range(self.frame_count):
            frame = self.build_frame(index)
            layer = frame.build_layer(index)
            layer.add_to(m)
            layer_names.append(layer.get_name())
            labels.append(frame.label)

        control = _AnimationControl(
            map_name=m.get_name(),
            layer_names=layer_names,
            labels=labels,
            interval_ms=int(self.interval_seconds * 1000),
        )
        m.get_root().add_child(control)
        return m

    def to_html(self, path: str) -> str:
        """Render the animation and save it as a standalone HTML file. Returns the path written."""
        out_dir = os.path.dirname(path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        self.render().save(path)
        return path
