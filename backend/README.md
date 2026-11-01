# Backend

FastAPI service that turns target shadow images into a 3D tree whose projections
match them (Space Colonization Algorithm). See the [root README](../README.md)
for the algorithm overview and API summary.

```bash
uv run uvicorn main:app --reload   # http://localhost:8000, docs at /docs
uv run pytest                      # run the test suite
LOG_LEVEL=DEBUG uv run uvicorn main:app   # verbose logging
```

Module map: `voxel.py` (attractors/repulsors) → `sca.py` (growth) →
`shadow.py` (render + fitness), with shared helpers in `projection.py`,
schemas in `models.py`, limits and bounds in `config.py`, and routes in
`routers/scenes.py`. Tests live in `tests/` and use images from `../tests/images`.
