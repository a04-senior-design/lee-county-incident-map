"""
This module defines the GiStarHeatmap class, which uses the G_Local class from
the esda.getisord package to build a Getis-Ord Gi* model from x-y coordinate
data points and a distance band (i.e. radius from the center of a cell).  
A grid of uniform square cells is defined and the counts of the data points falling
within each cell are used to perform the Getis-Ord Gi* analysis.  Cells whose
centroid falls outside of the "land_polygon" are not counted towards the mean,
standard deviation, or as neighbors in the analysis (with one caveat; 
all centroids with counts > 0 are included even if the centroid is outside of the polygon).
The class generates a PNG image of the resulting Gi* heat map.
"""

import os

import numpy as np
import matplotlib.pyplot as plt
import shapely
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.coords import BoundingBox
from rasterio.transform import from_origin, array_bounds
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.ticker import MaxNLocator
from libpysal.weights import DistanceBand, fill_diagonal
from esda.getisord import G_Local

class GiStarHeatMap:
    """Heat map class for generating a png image of a Getis-Ord Gi* z-score surface"""

    def __init__(self, points, distance_band, x_min, y_min, x_max, y_max, cell_size, land_polygon=None, output_dir="."):

        self.points = np.asarray(points)
        self.distance_band = distance_band

        if self.distance_band <= 0:
            raise ValueError(f"Distance Band must be > 0, got {self.distance_band}")

        self.x_min_grid = x_min
        self.y_min_grid = y_min
        self.x_max_grid = x_max
        self.y_max_grid = y_max
        self.cell_size = cell_size
        self.output_dir = output_dir
        # create a grid where cells will be used as boundaries to count the number of data points for the algorithm
        self.x_edges = np.arange(self.x_min_grid, self.x_max_grid + self.cell_size, self.cell_size)
        self.y_edges = np.arange(self.y_min_grid, self.y_max_grid + self.cell_size, self.cell_size)
        # determine the counts of points within each grid cell (also returns x_edges and y_edges)
        self.counts, _, _ = np.histogram2d(
            self.points[:, 0], self.points[:, 1], bins=[self.x_edges, self.y_edges]
        )
        # point count per cell (1-D arrY)
        self.y = self.counts.ravel()  
        # cell centroids, one per grid cell, in the same order as the flattened counts
        x_centers = (self.x_edges[:-1] + self.x_edges[1:]) / 2
        y_centers = (self.y_edges[:-1] + self.y_edges[1:]) / 2
        # x-y coordinates of each cell center, shape (nx, ny) to match self.counts
        cx, cy = np.meshgrid(x_centers, y_centers, indexing='ij')
        # (nx * ny, 2) array of [x, y] cell centers, same order as self.counts.ravel()
        self.cell_centroids = np.column_stack([cx.ravel(), cy.ravel()])
        # land mask: True for cells included in the Gi* analysis
        self.land_cells = self._land_cells(land_polygon)
        # counts and centroid for land cells only, which are the inputs to the Gi* analysis
        self.y_land = self.y[self.land_cells]
        self.land_centroids = self.cell_centroids[self.land_cells]
        # create the weight matrix
        self.w = self._weight_matrix()
        # fit the gi* model
        self.gi_star = self._fit_gi_star_model()
        #z-scores and p-values for every cell in the full grid; water cells are NaN
        self.z_scores = np.full(self.y.shape, np.nan)
        self.z_scores[self.land_cells] = self.gi_star.Zs
        # p_norm output represents the p-values corresponding to the z-scores
        self.p_norm_val = np.full(self.y.shape, np.nan)
        self.p_norm_val[self.land_cells] = self.gi_star.p_norm


    def _land_cells(self, land_polygon):
        # no land polygon given: every cell is included in the analysis
        if land_polygon is None:
            return np.ones(self.y.shape, dtype=bool)
        # a cell is land if its center falls inside (or on the boundary of) the land polygon
        on_land = shapely.intersects_xy(land_polygon, self.cell_centroids[:, 0], self.cell_centroids[:, 1])
        # always keep cells that contain incidents, so no incident is dropped
        return on_land | (self.y > 0)


    def _weight_matrix(self):
        # spatial weight matrix using a fixed-distance band and binary weights of 1
        w = DistanceBand(self.land_centroids, threshold=self.distance_band, binary=True)
        # self-weight = 1, which is what makes this Gi* rather than Gi
        w = fill_diagonal(w, val=1.0)  
        return w


    def _fit_gi_star_model(self):
        # instantiate object of class G_Local to perform the Gi* algorithm
        gi_star = G_Local(self.y_land, self.w, transform='R', star=True, permutations=0)
        return gi_star


    def print_z_scores(self, min_points=0):
        print(f"Gi* z-scores (grid cells with at least {min_points} points):")
        for centroid, count, z, p, land in zip(self.cell_centroids, self.y, self.z_scores, self.p_norm_val, self.land_cells):
            if land and count >= min_points:
                print(f"  cell centroid ({centroid[0]:.3f}, {centroid[1]:.3f}): count = {int(count)}, Z = {z:.3f}, p = {p:.3f}")


    def generate_zscore_heatmap_image(self, filename="z_score_overlay.png", pixels_per_cell=10, z_abs_max=None):
        # z_abs_max lets animation frames share one color scale; the default keeps the per-image scale

        # z-scores as a north-up grid: transpose (nx, ny) -> (ny, nx) so rows are y,
        # then flip so the first row is the northernmost row of cells
        z_grid = np.flipud(self.z_scores.reshape(self.counts.shape).T).astype("float32")

        # upsample so each cell is pixels_per_cell x pixels_per_cell pixels; this keeps the
        # blocks crisp after reprojection and when the browser stretches the image
        src_array = np.repeat(np.repeat(z_grid, pixels_per_cell, axis=0), pixels_per_cell, axis=1)
        pixel_size = self.cell_size / pixels_per_cell

        # transform from pixel coordinates to real-world spatial coordinates,
        # anchored at the top-left corner of the grid (cell edges, not centers)
        transform_src = from_origin(self.x_edges[0], self.y_edges[-1], pixel_size, pixel_size)
        src_height, src_width = src_array.shape
        src_bounds = array_bounds(src_height, src_width, transform_src)  # west, south, east, north

        # re-project the z-score grid into latitude/longitude in memory
        dst_transform, width, height = calculate_default_transform(
            "EPSG:2882", "EPSG:4326", src_width, src_height, *src_bounds
        )
        # start with NaN so areas outside the grid stay "no data" rather than becoming Z = 0
        warped = np.full((height, width), np.nan, dtype="float32")

        reproject(
            source=src_array,
            destination=warped,
            src_transform=transform_src,
            src_crs="EPSG:2882",
            src_nodata=np.nan,
            dst_transform=dst_transform,
            dst_crs="EPSG:4326",
            dst_nodata=np.nan,
            resampling=Resampling.nearest,  # nearest keeps each cell a solid block
        )

        # min/max boundary coordinates in latitude/longitude
        bounds = BoundingBox(*array_bounds(height, width, dst_transform))

        # color map for coloring the heat map (unchanged)
        colors = [
            (0.0,   (0, 0, 1, 1)),        # Z = -3 blue
            (0.2,   (0.5, 0.5, 1, 0.6)),  # Z = -1.8 light blue
            (0.5,   (1, 1, 1, 0)),        # Z =  0 fully transparent
            (0.583, (1, 1, 0, 0.15)),     # Z =  0.5 pale yellow
            (0.75,  (1, 1, 0, 0.7)),      # Z =  1.5 yellow
            (0.83,  (1, 0.6, 0, 0.85)),   # Z =  2.0 orange
            (0.958, (1, 0, 0, 1)),        # Z =  2.75 bright red
            (1.0,   (1, 0, 0, 1)),        # Z =  3.0: still bright red
        ]
        cmap = LinearSegmentedColormap.from_list('gi_star_fade', colors)
        cmap.set_bad(alpha=0)  # NaN (no data) pixels are fully transparent

        # diverging norm centered at 0 so blue/red are symmetric (unchanged)
        if z_abs_max is None:
            finite_z = self.z_scores[np.isfinite(self.z_scores)]
            z_abs_max = max(np.abs(finite_z).max(), 1e-6) if finite_z.size else 1.0
        # z-scores beyond the scale get its end colors
        norm = TwoSlopeNorm(vmin=-z_abs_max, vcenter=0, vmax=z_abs_max)

        # apply the norm and colormap to the reprojected z-scores
        rgba = cmap(norm(np.ma.masked_invalid(warped)), bytes=True)

        # stash for the legend
        self.legend_vmin = -z_abs_max
        self.legend_vmax = z_abs_max
        self.legend_norm = norm
        self.legend_cmap = cmap

        # write the colorized array out to a PNG file
        plt.imsave(os.path.join(self.output_dir, filename), rgba)

        # being returned to define the bounds
        return bounds


    def get_legend_data(self, n_ticks=7, caption="Gi* z-score"):
        """
        Build JSON-serializable legend data mirroring the overlay's color
        mapping, for rendering as an HTML/CSS legend on the frontend.

        Must be called after generate_zscore_heatmap_image(), which sets the
        legend's vmin, vmax, norm and colormap.
        """
        # sample the color gradient across the full z-score range
        n_samples = 256
        sample_values = np.linspace(self.legend_vmin, self.legend_vmax, n_samples)
        sampled_colors = self.legend_cmap(self.legend_norm(sample_values))

        # convert RGBA (0-1 range) to hex strings for CSS gradients; hex has no alpha,
        # so blend each color with white to show how semi-transparent colors actually look
        hex_colors = []
        for r, g, b, a in sampled_colors:
            r, g, b = (a * c + (1 - a) for c in (r, g, b))
            hex_colors.append(
                "#{:02x}{:02x}{:02x}".format(int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))
            )

        # "nice" round tick positions, symmetric around 0
        locator = MaxNLocator(nbins=n_ticks, symmetric=True, min_n_ticks=3)
        nice_ticks = [
            float(t) for t in locator.tick_values(self.legend_vmin, self.legend_vmax)
            if self.legend_vmin <= t <= self.legend_vmax
        ]

        # always include the true min/max explicitly, deduped against nice_ticks
        all_ticks = sorted(
            set(nice_ticks) | {round(float(self.legend_vmin), 2), round(float(self.legend_vmax), 2)}
        )

        return {
            "colors": hex_colors,
            "vmin": float(self.legend_vmin),
            "vmax": float(self.legend_vmax),
            "ticks": all_ticks,
            "caption": caption,
        }


    def generate_zscore_printable_heatmap_image(self, filename="z_score_figure.png"):

        # reshape z-scores back into the grid shape for imaging
        z_grid = self.z_scores.reshape(self.counts.shape)

        # color map for coloring the heat map
        colors = [
            (0.0,   (0, 0, 1, 1)),        # Z = -3 blue
            (0.2,   (0.5, 0.5, 1, 0.6)),  # Z = -1.8 light blue
            (0.5,   (1, 1, 1, 0)),        # Z =  0 fully transparent
            (0.583, (1, 1, 0, 0.15)),     # Z =  0.5 pale yellow
            (0.75,  (1, 1, 0, 0.7)),      # Z =  1.5 yellow
            (0.83, (1, 0.6, 0, 0.85)),   # Z =  2.0 orange
            (0.958, (1, 0, 0, 1)),        # Z =  2.75 bright red
            (1.0,   (1, 0, 0, 1)),        # Z =  3.0: still bright red
        ]

        heat_cmap = LinearSegmentedColormap.from_list('gi_star_fade', colors)

        # set the figure size to 8x8
        fig, ax = plt.subplots(figsize=(8, 8))
        cmap = heat_cmap.copy()
        cmap.set_bad(alpha=0)

        # diverging norm centered at 0 so blue/red are symmetric around "not significant"
        finite_z = z_grid[np.isfinite(z_grid)]
        z_abs_max = max(np.abs(finite_z).max(), 1e-6) if finite_z.size else 1.0
        norm = TwoSlopeNorm(vmin=-z_abs_max, vcenter=0, vmax=z_abs_max)

        # create the image and output as a png file
        im = ax.pcolormesh(
            self.x_edges,
            self.y_edges,
            np.ma.masked_invalid(z_grid.T),
            cmap=cmap,
            norm=norm,
            shading='flat',
        )
        ax.set_aspect('equal')

        ax.hlines(self.y_edges, xmin=self.x_edges[0], xmax=self.x_edges[-1], color='gray', linewidth=0.5, alpha=0.5, zorder=3)
        ax.vlines(self.x_edges, ymin=self.y_edges[0], ymax=self.y_edges[-1], color='gray', linewidth=0.5, alpha=0.5, zorder=3)

        ax.set_xlim(xmin=self.x_edges[0], xmax=self.x_edges[-1])
        ax.set_ylim(ymin=self.y_edges[0], ymax=self.y_edges[-1])

        ax.scatter(self.points[:, 0], self.points[:, 1], c='black', s=15, zorder=5, label='data points')

        fig.colorbar(im, ax=ax, label='Gi* z-score')
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_title('Getis-Ord Gi* Hot Spot / Cold Spot Surface')
        ax.legend(loc='upper right')

        plt.savefig(filename, dpi=300, bbox_inches='tight', transparent=True)
        plt.close()





def main():
    print("Running the GiStarHeatMap module directly")

    # test input data that represents two x-y coordinates on a map
    data_points = np.array([[10.5, 10.5], [20.5, 26.5], [15.1, 15.2], [12.5, 20.1], [22, 15.2], [11, 15.3], [12.6, 16], [12.4, 18.1], [13.3, 17.4], [13.5, 12.9]])

    # define grid properties
    x_min = 0
    y_min = 0
    x_max = 50
    y_max = 50
    cell_size = 3.0

    # neighbors = cell centroids within this radius
    distance_band = cell_size * 1.5  

    #instantiate GiStarHeatMap object
    gi_star_obj = GiStarHeatMap(points=data_points, distance_band=distance_band, x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max, cell_size=cell_size, land_polygon=None, output_dir=".")

    # generate png image of the z-scores
    gi_star_obj.generate_zscore_heatmap_image("test_gi_star_surface.png")

    # print z-scores from the analysis
    gi_star_obj.print_z_scores()

    

if __name__ == "__main__":
    main()

