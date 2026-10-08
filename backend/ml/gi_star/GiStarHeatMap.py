"""
This module defines the GiStarHeatmap class, which uses the G_Local class from
the esda.getisord package to build a Getis-Ord Gi* model from x-y coordinate
data points and a distance band (i.e. radius from the center of a cell).  
A grid of uniform square cells is defined and the counts of the data points falling
within each cell are used to perform the Getis-Ord Gi* analysis.  
The class generates a PNG image of the resulting Gi* heat map.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from libpysal.weights import DistanceBand, fill_diagonal
from esda.getisord import G_Local

class GiStarHeatMap:
    """Heat map class for generating a png image of a Getis-Ord Gi* z-score surface"""

    def __init__(self, points, distance_band, x_len, y_len, cell_size):

        self.points = np.asarray(points)
        self.distance_band = distance_band
        self.x_len = x_len
        self.y_len = y_len
        self.cell_size = cell_size
        # create a x_len x y_len grid where cells will be used as boundaries to count the number of data points for the algorithm
        self.x_edges = np.arange(0, self.x_len + self.cell_size, self.cell_size)
        self.y_edges = np.arange(0, self.y_len + self.cell_size, self.cell_size)

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
        # create the weight matrix
        self.w = self._weight_matrix()
        # fit the gi* model
        self.gi_star = self._fit_gi_star_model()
        # Zs output represents the observed Gi* which is equivalent to the z-score
        self.z_scores = self.gi_star.Zs
        # p_sim output represents the p-values of each cell for the model simulated random distribution
        self.p_values = self.gi_star.p_sim

    def _weight_matrix(self):

        # spatial weight matrix using a fixed-distance band and binary weights of 1
        w = DistanceBand(self.cell_centroids, threshold=self.distance_band, binary=True)
        # self-weight = 1, which is what makes this Gi* rather than Gi
        w = fill_diagonal(w, val=1.0)  
        return w

    def _fit_gi_star_model(self):
        # instantiate object of class G_Local to perform the Gi* algorithm
        gi_star = G_Local(self.y, self.w, transform='R', star=True, permutations=999)
        return gi_star

    def print_z_scores(self, min_points=0):
        print(f"Gi* z-scores (grid cells with at {min_points} points):")
        for centroid, count, z, p in zip(self.cell_centroids, self.y, self.z_scores, self.p_values):
            if count >= min_points:
                print(f"  cell centroid ({centroid[0]:.3f}, {centroid[1]:.3f}): count = {int(count)}, Z = {z:.3f}, p = {p:.3f}")


    def generate_zscore_heatmap_image(self, filename="z_score_overlay.png"):

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
        im = ax.imshow(
            np.ma.masked_invalid(z_grid.T),
            origin='lower',
            extent=[0, self.x_len, 0, self.y_len],
            cmap=cmap,
            aspect='equal',
            interpolation='bilinear',
            norm=norm,
        )

        ax.vlines(self.x_edges, ymin=0, ymax=self.y_len, color='gray', linewidth=0.5, alpha=0.5, zorder=3)
        ax.hlines(self.y_edges, xmin=0, xmax=self.x_len, color='gray', linewidth=0.5, alpha=0.5, zorder=3)

        ax.set_xlim(0, self.x_len)
        ax.set_ylim(0, self.y_len)

        ax.scatter(self.points[:, 0], self.points[:, 1], c='black', s=15, zorder=5, label='data points')

        fig.colorbar(im, ax=ax, label='Gi* Z-score')
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

    # define length, width, and cell size of test grid
    x_len, y_len = 50, 50
    cell_size = 3.0

    # neighbors = cell centroids within this radius
    distance_band = cell_size * 1.5  

    #instantiate GiStarHeatMap object
    gi_star_obj = GiStarHeatMap(points=data_points, distance_band=distance_band, x_len=x_len, y_len=y_len, cell_size=cell_size)

    # generate png image of the z-scores
    gi_star_obj.generate_zscore_heatmap_image("test_gi_star_surface.png")

    # print z-scores from the analysis
    gi_star_obj.print_z_scores()

    

if __name__ == "__main__":
    main()

