"""
This module defines the KDEHeatMap class, which uses the FFTKDE class from
the KDEpy package to build a KDE (kernel density estimation) model from
x-y coordinate data points and a bandwidth corresponding to each cluster level.
The class generates a PNG image of the resulting KDE heat map.
"""

import time
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.colors import PowerNorm
from KDEpy import FFTKDE
from scipy.ndimage import gaussian_filter
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.transform import from_origin
import branca.colormap as bcm
from matplotlib.ticker import MaxNLocator

class KDEHeatMap:
    """Heat map class for generating a png image of a KDE density surface."""

    def __init__(self, points, cluster_levels, bandwidths, x_min, y_min, x_max, y_max, increment, output_dir="."):

        self.points = np.asarray(points)
        self.cluster_levels = np.asarray(cluster_levels)
        # bandwidth in the order [bw0, bw1 (if applicable), bw2 (if applicable)] where bw0 is cluster=0, bw1 is cluster=1 (if applicable), bw2 is cluster=2 (if applicable) such that bw0>bw1>bw2
        self.bandwidths = np.asarray(bandwidths)
        self.x_min_lattice = x_min
        self.y_min_lattice = y_min
        self.x_max_lattice = x_max
        self.y_max_lattice = y_max
        self.increment_lattice = increment
        self.output_dir = output_dir
        self.x_coords = np.arange(x_min, x_max + increment, increment)
        self.y_coords = np.arange(y_min, y_max + increment, increment)
        xx, yy = np.meshgrid(self.x_coords, self.y_coords, indexing='ij')
        self.lattice = np.column_stack([xx.ravel(), yy.ravel()])
#        print(f'lattice.shape = {self.lattice.shape}')
        
        # separate points into clusters (number of clusters may vary from 1 to 3) -1==noise; 0==least dense; 1==denser than 0; 2==denser than 1
        # np.unique always returns a sorted array in ascending order
        unique_cluster_levels = np.unique(self.cluster_levels)
        self.points_per_cluster = []
        for cluster_level in unique_cluster_levels:
            # do not include points associated with noise
            if cluster_level != -1:
                mask = (self.cluster_levels == cluster_level)
                self.points_per_cluster.append(self.points[mask])

        # instantiate a FFTKDE object, one per bandwidth
        self.kde_obj_per_cluster = []
        self.rescale = []
        for bw in bandwidths:
            self.rescale.append(bw)
            kde_obj = FFTKDE(kernel='gaussian', bw=1.0)
            self.kde_obj_per_cluster.append(kde_obj)
        # fit each of the FFTKDE objects
        self.kde_model_per_cluster = self._fit_kde_model()
        # evaluate each of the FFTKDE objects for the grid lattice and get the summation
        self._density_surface = self._evaluate_kde_model()
#        print(f"KDEHeatMap self.bandwidths: {self.bandwidths}")
#        print(f'KDEHeatMap self.rescale: {self.rescale}')
#        print(f'KDEHeatMap cluster counts: {[len(cluster_points) for cluster_points in self.points_per_cluster]}')


    @property
    def density_surface(self):
        return self._density_surface

    def _fit_kde_model(self):
        # fit a kde model for each cluster of input data
        if len(self.kde_obj_per_cluster) != len(self.points_per_cluster):
            raise ValueError(
                f"Expected one bandwidth per cluster: got "
                f"{len(self.kde_obj_per_cluster)} bandwidths and "
                f"{len(self.points_per_cluster)} clusters."
            )
        kde_model_per_cluster = []
        for kde_obj, points, factor in zip(self.kde_obj_per_cluster, self.points_per_cluster, self.rescale):
            kde_model = kde_obj.fit(data=(points / factor))
#            # r_star represents FFTKDE's kernel truncation radius
#            r_star_implicit = kde_obj.kernel.practical_support(kde_obj.bw)
#            r_star_explicit = kde_obj.kernel.practical_support(kde_obj.bw, atol=1e-4)
#            if(r_star_implicit != r_star_explicit):
#                print(f"r_star unequal: {r_star_implicit} (implicit) vs {r_star_explicit} (explicit)")
#            else:
#                print(f"r_star: {r_star_implicit} (Kernel practical_support function)")
            kde_model_per_cluster.append(kde_model)
        return kde_model_per_cluster

    def _evaluate_kde_model(self):
        # apply the kde model to the mesh grid
#        start = time.perf_counter()
        density_surface_per_cluster = []
        for kde_model, factor in zip(self.kde_model_per_cluster, self.rescale):
            density_surface_scaled_1d = kde_model.evaluate(grid_points=(self.lattice / factor))            
            density_surface_rescaled_2d = density_surface_scaled_1d.reshape(self.x_coords.shape[0], self.y_coords.shape[0]) / factor**2
            density_surface_per_cluster.append(density_surface_rescaled_2d)
        # summation represents the density surface of the full model    
        density_surface = np.sum(density_surface_per_cluster, axis=0)
#        end = time.perf_counter()
#        print(f'time to compute density_surface: {end - start:.4f} seconds')
#        print(f'density_surface.shape = {density_surface.shape}')
        return density_surface

    def generate_heatmap_image(self):
        # reshape the density values to a rectangular grid
        density_grid = self._density_surface.reshape(self.x_coords.shape[0], self.y_coords.shape[0]).T

        # set a threshold for removing very low density values
        threshold_percentile = np.percentile(density_grid, 0.01)
        threshold_based_on_max = density_grid.max() * 0.0001
        threshold = max(threshold_percentile, threshold_based_on_max)
        density_grid_masked = np.ma.masked_where(density_grid < threshold, density_grid)

        # color map for coloring the heat map
        colors = [
            (0, 0, 1, 0),      # transparent blue (lowest density)
            (0, 0, 1, 1),      # opaque blue
            (1, 1, 0, 1),      # yellow
            (1, 0.5, 0, 1),    # orange
            (1, 0, 0, 1),      # red (highest density)
        ]

        heat_cmap = LinearSegmentedColormap.from_list('heat_fade', colors)

        # set the figure size to 8-inches x 8-inches
        fig, ax = plt.subplots(figsize=(8, 8))
        cmap = heat_cmap.copy()
        cmap.set_bad(alpha=0)

        vmin = threshold
        vmax = density_grid.max()
        norm_obj = PowerNorm(gamma=0.5, vmin=vmin, vmax=vmax)

        # create the image and output as a png file
        im = ax.imshow(
            density_grid_masked,
            origin='lower',
            extent=[self.x_min_lattice, self.x_max_lattice, self.y_min_lattice, self.y_max_lattice],
            cmap=cmap,
            aspect='equal',
            interpolation='bilinear',
            norm=norm_obj
        )

        # ax.axis('off')
        fig.colorbar(im, ax=ax, label='Density')
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_title('KDE Density Surface')

        plt.savefig(os.path.join(self.output_dir, 'density_surface.png'), dpi=300, bbox_inches='tight', transparent=True)
        plt.close()

        # transform from pixel coordinates to real-world spatial coordinates
        transform_src = from_origin(self.x_min_lattice, self.y_max_lattice, self.increment_lattice, self.increment_lattice)

        src_meta = {
            "driver": "GTiff",
            "height": density_grid_masked.shape[0],
            "width": density_grid_masked.shape[1],
            "count": 1,
            "dtype": "float32",
            "crs": "EPSG:2882",
            "transform": transform_src
        }

        # create tif file with the masked density surface values and coordinates
        with rasterio.open(os.path.join(self.output_dir, 'density_src.tif'), "w", **src_meta) as dst:
            dst.write(np.flipud(density_grid_masked.filled(0)).astype("float32"), 1)

        # re-project the tif file into latitude/longitude coordinate system
        with rasterio.open(os.path.join(self.output_dir, 'density_src.tif')) as src:
            dst_transform, width, height = calculate_default_transform(
                src.crs, "EPSG:4326", src.width, src.height, *src.bounds
            )
            dst_meta = src.meta.copy()
            dst_meta.update({
                "crs": "EPSG:4326",
                "transform": dst_transform,
                "width": width,
                "height": height,
            })

            with rasterio.open(os.path.join(self.output_dir, 'density_wgs84.tif'), "w", **dst_meta) as dst:
                reproject(
                    source=rasterio.band(src, 1),
                    destination=rasterio.band(dst, 1),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=dst_transform,
                    dst_crs="EPSG:4326",
                    resampling=Resampling.bilinear,
                )

        # retrieve the pixel values and min/max boundary coordinates from the tif file
        with rasterio.open(os.path.join(self.output_dir, 'density_wgs84.tif')) as src:
            warped = src.read(1)
            bounds = src.bounds  # left, bottom, right, top in lat/lon

        # normalization object that maps data values from 0 to 1 range
        normalized = norm_obj(warped)
        # apply color-coding from png file to the latitude/longitude re-projection
        rgba = cmap(normalized)

        # stash for the legend
        self.legend_vmin = vmin
        self.legend_vmax = vmax
        self.legend_norm = norm_obj
        self.legend_cmap = cmap

        # write the colorized array out to a PNG file
        plt.imsave(os.path.join(self.output_dir, 'density_overlay.png'), rgba)

        # being returned to define the bounds for Folium
        return bounds

    def get_legend_data(self, n_ticks=5, caption=None):
        """
        Build JSON-serializable legend data mirroring the overlay's color
        mapping, for rendering as an HTML/CSS legend on the frontend.
        Raw KDE density values are far too small for legible tick labels, so
        tick VALUES are rescaled by scale_factor purely for display. If
        scale_factor is not given, it's computed automatically so the max
        tick value lands near 10**target_magnitude (e.g. target_magnitude=2
        -> tick values land in the tens-to-hundreds range).
        The color mapping itself is untouched.
        """
        if self.legend_vmin > 0:
            exponent = np.floor(-np.log10(self.legend_vmin))
            scale_factor = 10 ** exponent
        else:
            scale_factor = 1.0

        if caption is None:
            caption = f'Incident Density (x {scale_factor:.0e})'

        # sample the color gradient in raw density units
        n_samples = 256
        sample_values = np.linspace(self.legend_vmin, self.legend_vmax, n_samples)
        normalized_samples = self.legend_norm(sample_values)
        sampled_colors = [self.legend_cmap(v) for v in normalized_samples]

        # convert RGBA float tuples (0-1 range) to hex strings for CSS gradients
        hex_colors = [
            "#{:02x}{:02x}{:02x}".format(
                int(round(r * 255)), int(round(g * 255)), int(round(b * 255))
            )
            for r, g, b, a in sampled_colors
        ]

        # rescaled domain, purely for legible tick labels
        vmin_scaled = self.legend_vmin * scale_factor
        vmax_scaled = self.legend_vmax * scale_factor

        # pick a small number of "nice" round tick positions instead of raw linspace,
        # which avoids values that all round to the same displayed digits
        locator = MaxNLocator(nbins=n_ticks, min_n_ticks=3)
        nice_ticks = [
            float(t) for t in locator.tick_values(vmin_scaled, vmax_scaled)
            if vmin_scaled <= t <= vmax_scaled
        ]

        # always include the true min/max explicitly, deduped against nice_ticks
        all_ticks = sorted(set(nice_ticks) | {float(vmin_scaled), float(vmax_scaled)})

        return {
            "colors": hex_colors,
            "vmin": float(vmin_scaled),
            "vmax": float(vmax_scaled),
            "ticks": all_ticks,
            "caption": caption,
        }










