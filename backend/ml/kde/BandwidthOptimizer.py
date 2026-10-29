"""
This module defines class BandwidthOptimizer, which finds the optimum KDE
bandwidth for each cluster level by mimimizing an objective function derived
from Negative-Log Likelihood (NLL) with Leave-One-Out (LOO) Cross-Validation (CV).
The likelihood is computed from the density surface produced by a KDE model
at the candidate bandwidths, using the FFTKDE class from the KDEpy package.
"""

import time
from KDEHeatMap import KDEHeatMap
import numpy as np
from scipy.optimize import minimize
from scipy.interpolate import RegularGridInterpolator
from scipy.spatial.distance import cdist

class BandwidthOptimizer:

    # starting gaps between bandwidths, as fractions of the largest gap that keeps every level within the bounds
    # spread low / middle / high since one start can settle in a local minimum
    CANDIDATE_START_FRACTIONS = np.array([0.03, 0.3, 0.9])
    # points whose grid leave-one-out density is below this fraction of their own kernel peak are recomputed exactly
    EXACT_RECOMPUTE_FRACTION = 0.01
    # maximum number of points recomputed exactly per evaluation, to bound runtime;
    # above this, the grid value is kept, on the assumption that more than this many isolated points only occur at smaller bandwidths that score worse than the optimum
    MAX_EXACT_RECOMPUTE_POINTS = 500
    # Nelder-Mead stopping tolerances. Nelder-Mead keeps a group of trial bandwidth sets (one more set than there are
    # bandwidths, e.g. 4 sets of 3 bandwidths). Each step replaces the worst set with a better one, so the group moves
    # toward the optimum and shrinks around it; it stops when both of these are met.
    #   xatol: every set is within this of the best set in each log-gap (a log difference of 0.01 is about a 1% change
    #     in a gap between bandwidths, under 2 ft for a 684 ft bandwidth); this sets the precision of the result
    #   fatol: every set's objective value is within this of the best set's; the objective is flat near the optimum,
    #     so this alone would not pin down the bandwidths - it only needs to be loose enough not to delay stopping
    #     once xatol is met
    NM_XATOL = 0.02
    NM_FATOL = 0.1

    def __init__(self, points, cluster_levels, x_min, y_min, x_max, y_max, increment, lower_bound=500, upper_bound=10000):

        self.points = np.asarray(points)
        self.cluster_levels = np.asarray(cluster_levels)
        # no input points - there is nothing to optimize over
        if len(self.points) == 0:
            raise ValueError("No points were given; at least two non-noise points are required to optimize bandwidths.")
        # one cluster level is needed per point
        if len(self.points) != len(self.cluster_levels):
            raise ValueError(f"Expected one cluster level per point: got {len(self.points)} points and {len(self.cluster_levels)} cluster levels.")
        # lowest and highest acceptable bandwidth values
        if not (np.isfinite(lower_bound) and np.isfinite(upper_bound)):
            raise ValueError(f"Bandwidth bounds must be finite: got lower_bound={lower_bound}, upper_bound={upper_bound}.")
        if lower_bound <= 0:
            raise ValueError(f"lower_bound must be > 0: got {lower_bound}")
        if upper_bound <= lower_bound:
            raise ValueError(f"upper_bound must be greater than lower_bound: got lower_bound={lower_bound}, upper_bound={upper_bound}.")
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound
        self.x_min_lattice = x_min
        self.y_min_lattice = y_min
        self.x_max_lattice = x_max
        self.y_max_lattice = y_max
        self.increment_lattice = increment
        self.x_coords = np.arange(x_min, x_max + increment, increment)
        self.y_coords = np.arange(y_min, y_max + increment, increment)  
        # separate points into clusters (number of clusters may vary from 1 to 3) -1==noise; 0==least dense; 1==denser than 0; 2==denser than 1
        unique_cluster_levels = np.unique(self.cluster_levels)
        self.num_bandwidths = np.count_nonzero(unique_cluster_levels != -1)
        self.points_per_cluster = []
        for cluster_level in unique_cluster_levels:
            # do not include points associated with noise
            if cluster_level != -1:
                mask = (self.cluster_levels == cluster_level)
                self.points_per_cluster.append(self.points[mask])
        self.cluster_sizes = [len(pts) for pts in self.points_per_cluster]
        n_non_noise_points = sum(self.cluster_sizes)
        # every point is noise - there is no cluster to optimize a bandwidth for
        if n_non_noise_points == 0:
            raise ValueError("All points are noise (cluster level of -1); at least one cluster level is required to optimize bandwidths.")
        # leave-one-out divided by (N - 1), so at least two non-noise points are needed 
        if n_non_noise_points < 2:
            raise ValueError(f"At least two non-noise points are required for leave-one-out cross-validation; got {n_non_noise_points}.")
        self.arranged_points = np.concatenate(self.points_per_cluster)
        self.num_arranged_points = len(self.arranged_points)
        # largest equal gap that keeps every level within the bounds: lower_bound + num_bandwidths * gap <= upper_bound
        max_start_diff = (self.upper_bound - self.lower_bound) / self.num_bandwidths
        # list of start diffs, each element is an array of size num_bandwidths
        self.candidate_start_bw_diffs = [np.full(self.num_bandwidths, diff) for diff in self.CANDIDATE_START_FRACTIONS * max_start_diff]

    def _unpack_bandwidths(self, bw_log_diffs: list[float]) -> np.ndarray:
        """function ensures bandwidth bounds for optimization input is 
        array of log(bw_i - bw_i+1) for i<(n-1) and log(val_i+lower_bound) for i==n
        output is array of band widths such that bw_i > bw_i+1 and bw_i > 0"""

        if len(bw_log_diffs) != self.num_bandwidths:
            raise ValueError(
                f"Expected number of bandwidth diffs to match number of bandwidths: got "
                f"{len(bw_log_diffs)} bandwidth diffs while "
                f"number of bandwidths is {self.num_bandwidths}."
            )
        # reverse such that bandwidth increases as index increases
        reversed_bw_log_diffs = bw_log_diffs[::-1].copy()
        reversed_bandwidths = np.zeros(self.num_bandwidths)
        for i, bw_log_diff in enumerate(reversed_bw_log_diffs):
            if i == 0:
                reversed_bandwidths[i] = self.lower_bound + np.exp(bw_log_diff)
            elif i > 0:
                reversed_bandwidths[i] = reversed_bandwidths[i - 1] + np.exp(bw_log_diff)
        bandwidths = reversed_bandwidths[::-1].copy()
        return bandwidths

    def _gaussian_peak_2d(self, bandwidth):
        """peak value of 2D gaussian distribution for bandwidth input"""
        return 1.0 / (2 * np.pi * bandwidth**2)

    def _loo_neg_log_likelihood(self, cur_bw_log_diffs: np.ndarray):
        """objective function for the optimizer; input is in log-diff space."""
        cur_bw_log_diffs = np.asarray(cur_bw_log_diffs)
        bandwidths = self._unpack_bandwidths(cur_bw_log_diffs)
        return self._loo_neg_log_likelihood_from_bandwidths(bandwidths)

    def _loo_neg_log_likelihood_from_bandwidths(self, bandwidths: np.ndarray):
        """objective function for negative log-likelihood of leave-one-out cross-validation;
        input is ACTUAL bandwidth values (not log-diffs)
        output is negative log-likelihood for input bandwidths"""
        
        bandwidths = np.asarray(bandwidths)
        
        # large penalty for bandwidths above the upper bound, or overflowed to inf by the log-diff unpacking,
        # so the minimizer is pushed back without building a KDE model        
        if not np.all(np.isfinite(bandwidths)) or np.any(bandwidths > self.upper_bound):
            return 1e10

#        start = time.perf_counter()
        bw_per_arranged_points = np.repeat(bandwidths, self.cluster_sizes)

        # density of the grid
        kde_obj = KDEHeatMap(points=self.points, cluster_levels=self.cluster_levels, bandwidths=bandwidths, x_min=self.x_min_lattice, y_min=self.y_min_lattice, x_max=self.x_max_lattice, y_max=self.y_max_lattice, increment=self.increment_lattice, output_dir=".")
        f_grid_2d = kde_obj.density_surface

        # interpolate density surface at input data points
        interpolator = RegularGridInterpolator(
            (self.x_coords, self.y_coords), f_grid_2d, bounds_error=False, fill_value=1e-300
        )
        f_at_arranged_points = interpolator(self.arranged_points)

        N = self.num_arranged_points
        # represents the gaussian corresponding to each data point
        self_term = self._gaussian_peak_2d(bw_per_arranged_points)
        # leave-one-out density
        f_loo = (N * f_at_arranged_points - self_term) / (N - 1)
        # the grid underestimates each point's own peak slightly, so for an isolated point the subtraction above can go to
        # zero or below even though its true leave-one-out density is small but positive; recompute those points exactly
        flagged = np.flatnonzero(f_loo < self.EXACT_RECOMPUTE_FRACTION * self_term / (N - 1))
        has_flagged_points = len(flagged) > 0
        within_recompute_cap = len(flagged) <= self.MAX_EXACT_RECOMPUTE_POINTS
        if has_flagged_points and within_recompute_cap:
            # squared distance from each flagged point to every point
            sq_distances = cdist(self.arranged_points[flagged], self.arranged_points, 'sqeuclidean')
            # kernel[i, j] is point j's gaussian (with point j's bandwidth) evaluated at flagged point i
            kernel = np.exp(-sq_distances / (2 * bw_per_arranged_points**2)) / (2 * np.pi * bw_per_arranged_points**2)
            # a flagged point doesn't count its own kernel
            kernel[np.arange(len(flagged)), flagged] = 0.0
            f_loo[flagged] = kernel.sum(axis=1) / (N - 1)

        # set values < 1e-300 to 1e-300 (namely to guard against log(0))
        f_loo = np.clip(f_loo, 1e-300, None)

#        end = time.perf_counter()
#        print(f'time in _loo_neg_log_likelihood_from_bandwidths: {end - start:.4f} seconds')
        # negative log-likelihood
        return -np.sum(np.log(f_loo))
        
   
    def optimize_bandwidths(self):
        """function finds the optimum bandwidth - runs the optimizer from multiple starting gaps and keeps the best result"""

        self.best_result = None

        for bw_guess_diffs in self.candidate_start_bw_diffs:
            initial_bw_log_diffs = np.log(bw_guess_diffs)
            res = minimize(fun=self._loo_neg_log_likelihood, x0=initial_bw_log_diffs, args=(), method='Nelder-Mead', options={'xatol': self.NM_XATOL, 'fatol': self.NM_FATOL})
            print(f'initial_bw_log_diffs: {initial_bw_log_diffs}  res.message: {res.message}')
            print(f'objective: {res.fun}')
            print(f'bandwidth: {self._unpack_bandwidths(res.x)}')
            if self.best_result is None or res.fun < self.best_result.fun:
                self.best_result = res

        print("best objective:", self.best_result.fun)
        print("best bandwidth:", self._unpack_bandwidths(self.best_result.x))

        return self._unpack_bandwidths(self.best_result.x)

    def brute_force_optimizer(self, increment, max_allowable_bandwidth):
        """used for testing - function scans through a range of possible bandwidths, starting at the lower bound, given an increment and maximum bandwidth"""
        if increment <= 0:
            raise ValueError(f'increment should be > 0 but it is currently {increment}')
        if max_allowable_bandwidth <= self.lower_bound:
            raise ValueError(f'maximum allowable bandwidth should be greater than the lower bound of {self.lower_bound}')
        return self._brute_force_optimizer_helper([self.lower_bound], self.num_bandwidths - 1, increment, max_allowable_bandwidth)

    def _brute_force_optimizer_helper(self, bandwidths, n_bandwidths_remaining, increment, max_allowable_bandwidth):
        """function is a helper for the function brute_force_optimizer.  it returns a list of [[bandwidths], NLL value]"""
        res = []
        h_last = bandwidths[-1]

        if h_last > max_allowable_bandwidth:
            return []

        if n_bandwidths_remaining == 0:
            bw_snapshot = bandwidths[::-1]
            res.append([bw_snapshot, self._loo_neg_log_likelihood_from_bandwidths(bandwidths=bw_snapshot)])

        if n_bandwidths_remaining > 0:
            bandwidths.append(h_last + increment)
            res += self._brute_force_optimizer_helper(bandwidths, n_bandwidths_remaining - 1, increment, max_allowable_bandwidth)    
            bandwidths.pop()
        
        bandwidths[-1] += increment
        res += self._brute_force_optimizer_helper(bandwidths, n_bandwidths_remaining, increment, max_allowable_bandwidth)
        bandwidths[-1] -= increment

        return res




