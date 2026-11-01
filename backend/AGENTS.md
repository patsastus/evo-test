# Backend Agent Instructions: Multi-Shadow Colonization Generator

## Role & Goal
You are an expert Python backend developer specializing in procedural 3D generation and computational geometry. We are building a Space Colonization Algorithm (SCA) to generate a single 3D tree structure that casts *distinctly different 2D shadows* when lit from different angles (e.g., a corner-lit shadow sculpture).

## Tech Stack (Strictly Enforced)
* **Language:** Python 3.12+
* **Framework:** FastAPI
* **Package Manager:** `uv`
* **Libraries:** `pydantic` (schemas), `Pillow` (image processing), `numpy` (vector math/ray intersection)

## The Core Algorithm (Multi-Projection SCA)
We are generating trees in a 3D bounding box (X: [-5, 5], Z: [-5, 5], Y: [0, 10]). The generation process follows these phases:

1. **Phase 1: The Intersection Volume (The Attractors)**
   - The system receives multiple target shadows, each paired with a specific light source vector and projection plane (e.g., Light A points down the X-axis onto the Z-Y plane; Light B points down the Z-axis onto the X-Y plane).
   - Extrude the "dark pixels" of each shadow along their respective light vectors to create 3D voxel rays.
   - Calculate the 3D boolean intersection where ALL extruded shadow volumes overlap.
   - Populate this overlapping 3D space with a cloud of "Attractor Points."
2. **Phase 2: Space Colonization (The Growth)**
   - Start with a root node at `(0, 0, 0)`.
   - Grow branches toward the Attractor Points using standard SCA (calculate normalized growth vectors toward nearest attractors within a specific radius).
   - Cull attractors as branches reach them (kill distance).
3. **Phase 3: Geometry & Contract**
   - Convert the resulting node graph into the exact `TreeNode` and `SceneData` Pydantic models expected by the frontend.

## Workflow & Boundaries
1. **Pace Yourself:** All three phases are implemented (`voxel.py`, `sca.py`, `shadow.py`/`models.py`). Make incremental changes and keep `backend/tests` passing.
2. **Frontend Contract:** Do NOT break the existing `models.py`. The `POST /scenes/generate` endpoint must still return valid `SceneData` (inside `GenerateResponse`).
3. **Canvas to PIL:** All 2D image processing and pixel sampling must be done using `Pillow`.
