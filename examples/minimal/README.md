# Minimal public example

This example contains no private art or model output. Generate its tiny synthetic reference, then build the same five-page `.fig` contract used by consumer jobs:

```powershell
python examples/minimal/create_reference.py
ui-rebuilder build examples/minimal/minimal.job.yaml --output Output/minimal --force
ui-rebuilder validate Output/minimal
```

After `python scripts/bootstrap.py --profile fig`, OpenPencil is discovered automatically at `third_party/open-pencil`; no absolute path is needed.
