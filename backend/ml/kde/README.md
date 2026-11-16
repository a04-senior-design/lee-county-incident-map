# KDEHeatMap and BandwidthOptimizer Unit Tests

Unit tests for two classes that share this folder and its test data:

- `KDEHeatMap` in `KDEHeatMap.py`: 29 test cases (TC-01 to TC-29), described in the **KDEHeatMap Unit Test Plan**.
- `BandwidthOptimizer` in `BandwidthOptimizer.py`: 8 test cases (BW-01 to BW-08), described in the **BandwidthOptimizer Unit Test Plan**.

Each plan gives the setup and expected result of every case. The two test files run independently.

## Folder layout

```
kde_unit_test/
├── README.md
├── requirements.txt
├── make_fixture.py
├── KDEHeatMap.py
├── BandwidthOptimizer.py
├── test_KDEHeatMap.py
├── test_BandwidthOptimizer.py
└── test_data/
    ├── two_clusters.csv
    ├── late-paper-81460214_production_neondb_2026-07-06_13-14-24.csv
    ├── density_scenario_1levels.txt
    ├── density_scenario_2levels.txt
    └── density_scenario_3levels.txt
```

`KDEHeatMap.py`, `BandwidthOptimizer.py` and the `test_data` folder must sit next to the test files. The tests find them relative to the test file, so the folder itself can be anywhere. `BandwidthOptimizer.py` uses `KDEHeatMap.py`, so the BandwidthOptimizer tests need both.

## Setup

All the packages are listed in `requirements.txt`, including scipy, which `BandwidthOptimizer.py` uses.

To set up a virtual environment in this folder and install them:

```
python3 -m venv venv
source venv/bin/activate
python3 -m pip install -r requirements.txt
```

In later sessions, run only `source venv/bin/activate` before running the tests.

## Running the tests

From the `kde_unit_test` folder:

| To | Run |
| --- | --- |
| Run every KDEHeatMap test | `python3 -m pytest test_KDEHeatMap.py -v` |
| Run every BandwidthOptimizer test | `python3 -m pytest test_BandwidthOptimizer.py -v` |
| Run the BandwidthOptimizer tests without the slow real-data case | `python3 -m pytest test_BandwidthOptimizer.py -k "not bw08" -v` |
| Run both files together | `python3 -m pytest -v` |
| Run a single test case | `python3 -m pytest test_BandwidthOptimizer.py::test_bw03_bandwidth_unpacking -v` |
| Measure KDEHeatMap coverage | `python3 -m pytest test_KDEHeatMap.py --cov=KDEHeatMap --cov-branch --cov-report=term-missing` |
| Measure BandwidthOptimizer coverage | `python3 -m pytest test_BandwidthOptimizer.py --cov=BandwidthOptimizer --cov-branch --cov-report=term-missing` |
| Measure coverage of both | `python3 -m pytest --cov=KDEHeatMap --cov=BandwidthOptimizer --cov-branch --cov-report=term-missing` |

## Expected results

| Test file | Result | Time |
| --- | --- | --- |
| `test_KDEHeatMap.py` | `42 passed` | A few seconds |
| `test_BandwidthOptimizer.py` | `23 passed` | Under two minutes, mostly BW-08 |
| Both together | `65 passed` | Under two minutes |

pytest reports more tests than there are cases because some cases try several inputs, and each input is reported on its own line. The label in brackets after a test name, such as `test_bw08_real_incident_data[2levels]`, shows which input ran.

- KDEHeatMap: TC-02, TC-04, TC-05, TC-07, TC-08, TC-09 and TC-29.
- BandwidthOptimizer: BW-01, BW-04, BW-05, BW-07 and BW-08. BW-04 is split into two test functions: inputs (a) to (d), and the isolated point (e).

Each coverage run should report `100%` of statements and branches. The combined run prints one row for each file.

Times vary by machine. pytest runs the files in alphabetical order, so `test_BandwidthOptimizer.py` runs first; the order doesn't affect the results.

In the output, `PASSED` (or `.`) means pass and `FAILED` (or `F`) means fail. A failing test prints the line that failed and the values it compared.

## Timing log

TC-18 builds a heat map from 10,000 points and appends its build and render times to `kde_timing_log.csv` in this folder on every run. The times are recorded rather than tested, since they vary by machine.

## Regenerating the synthetic data

`test_data/two_clusters.csv` is synthetic: 105 points in Lee County with known cluster labels. To recreate it:

```
python3 make_fixture.py
```

The random seed is fixed, so the script always produces the identical file.

## Notes

- If a file named `test_kde.py` is in the same folder, rename it (for example to `kde_demo.py`). pytest runs every file named `test_*.py`, and that file is a demo script, not a test.
- BW-04 compares the class's score with an exact leave-one-out calculation written in the test, and BW-06 compares the optimizer with `brute_force_optimizer`. If either fails after a change to `BandwidthOptimizer.py` or `KDEHeatMap.py`, the objective or the search has changed.
