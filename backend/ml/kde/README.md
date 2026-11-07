# KDEHeatMap Unit Tests

Unit tests for the `KDEHeatMap` class in `KDEHeatMap.py`. The 29 test cases (TC-01 to TC-29) are described in the **KDEHeatMap Unit Test Plan**, which gives the setup and expected result of each one.

## Folder layout

```
kde_unit_test/
├── README.md
├── requirements.txt
├── KDEHeatMap.py
├── test_KDEHeatMap.py
├── make_fixture.py
└── test_data/
    ├── two_clusters.csv
    ├── late-paper-81460214_production_neondb_2026-07-06_13-14-24.csv
    ├── density_scenario_1levels.txt
    ├── density_scenario_2levels.txt
    └── density_scenario_3levels.txt
```

`KDEHeatMap.py` and the `test_data` folder must sit next to `test_KDEHeatMap.py`. The tests find them relative to the test file, so the folder itself can be anywhere.

## Setup

The tests need the same packages as `KDEHeatMap.py` (numpy, matplotlib, KDEpy, rasterio), plus pandas and pyproj for the real-data test, and pytest with its coverage plugin. All of them are listed in `requirements.txt`.

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
| Run every test, one line each | `python3 -m pytest test_KDEHeatMap.py -v` |
| Run the tests whose names contain a keyword | `python3 -m pytest test_KDEHeatMap.py -k bandwidth -v` |
| Run a single test case | `python3 -m pytest test_KDEHeatMap.py::test_tc12_volume -v` |
| Measure statement and branch coverage | `python3 -m pytest test_KDEHeatMap.py --cov=KDEHeatMap --cov-branch --cov-report=term-missing` |

## Expected result

```
42 passed
```

pytest reports 42 tests for the 29 cases because seven cases (TC-02, TC-04, TC-05, TC-07, TC-08, TC-09 and TC-29) each try several inputs, and each input is reported on its own line. The label in brackets after a test name, such as `test_tc29_real_incident_data[2levels]`, shows which input ran.

The coverage run should report `100%` for `KDEHeatMap.py`.

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
- The warnings summary at the end of a run comes from matplotlib's notice that `cmap.set_bad` will be deprecated. It is raised inside `KDEHeatMap.py` and does not affect any result.
