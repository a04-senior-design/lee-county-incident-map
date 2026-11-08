# GiStarHeatMap Unit Tests

Unit tests for the `GiStarHeatMap` class in `GiStarHeatMap.py`. The 30 test cases (GI-01 to GI-30) are described in the **GiStarHeatMap Unit Test Plan**, which gives the setup and expected result of each one.

## Folder layout

```
gi_star_unit_test/
├── README.md
├── requirements.txt
├── GiStarHeatMap.py
├── test_GiStarHeatMap.py
└── test_data/
    ├── gi_star_example_data.csv
    └── late-paper-81460214_production_neondb_2026-07-06_13-14-24.csv
```

`GiStarHeatMap.py` and the `test_data` folder must sit next to `test_GiStarHeatMap.py`. The tests find them relative to the test file, so the folder itself can be anywhere.

## Setup

All the packages are listed in `requirements.txt`. To set up a virtual environment in this folder and install them:

```
python3 -m venv venv
source venv/bin/activate
python3 -m pip install -r requirements.txt
```

In later sessions, run only `source venv/bin/activate` before running the tests. The first run in a new environment can take a minute while matplotlib builds its font cache.

## Running the tests

From the `gi_star_unit_test` folder:

| To | Run |
| --- | --- |
| Run every test, one line each | `python3 -m pytest test_GiStarHeatMap.py -v` |
| Run the brute-force comparison only | `python3 -m pytest test_GiStarHeatMap.py -k brute -v` |
| Run a single test case | `python3 -m pytest test_GiStarHeatMap.py::test_gi15_hand_worked_cell -v` |
| Measure statement and branch coverage | `python3 -m pytest test_GiStarHeatMap.py --cov=GiStarHeatMap --cov-branch --cov-report=term-missing` |

## Expected result

```
44 passed
```

pytest reports 44 tests for the 30 cases because nine cases try several inputs (GI-02 through GI-05, GI-07, GI-11, GI-13, GI-22 and GI-27), and each input is reported on its own line. The label in brackets after a test name, such as `test_gi13_matches_brute_force_gi_star[10-2.796]`, shows which input ran.

The coverage run reports 100% of statements and branches in `GiStarHeatMap.py`. The line `if __name__ == "__main__":` is marked `# pragma: no cover`, since it's only true when the file is run directly; the `main()` demo itself is covered by GI-29.

The run should show no warnings.

## Timing log

GI-19 builds a heat map from 10,000 points at the app's settings and appends its build and render times to `gi_star_timing_log.csv` in this folder on every run. The times are recorded rather than tested, since they vary by machine.

## Notes

- GI-13, GI-14, GI-15 and GI-30 compare the class's z-scores with the standard Getis-Ord Gi* equation, calculated in the test. If `G_Local` is ever changed back from `transform='B'` to `transform='R'`, those cases fail, along with GI-27, which checks a printed z-score.
