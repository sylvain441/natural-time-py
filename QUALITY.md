# Quality Notes

## Reference

`natural-time-js` is the reference implementation. This repository is a Python port and must stay behaviorally aligned with the JavaScript package.

## Current Checks

Run from this repository:

```bash
python -m pip install -e .
python -m unittest discover -s tests
python -m compileall -q src tests
```

Additional spot checks have been run against selected `natural-time-js` golden vectors. The full vector suite is not automated yet.

## Known Gaps

- The port has not received a deep independent review.
- Full golden-vector validation should be automated before publishing a stable release.
- CI is not configured yet.
