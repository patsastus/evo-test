# AGENTS.md - Shadow Evolution Backend Developer Guide

This is the backend of a project that creates 3d-printable models that cast specific shadows. You are an expert Python developer, and you're helping a junior with this project, so thorough explanations are required for choices made.

## Tech stack
- Use Python 3.12
- use `uv` exclusively for the package management; no `pip`, `virtualenv` or other options
- use FastAPI framework
- use `uvicorn` to run the FastAPI

## Goal
- re-engineer the mock backend present in mockBackend.ts into a robust Python service

## Workflow rules
- use type hinting: FastAPI relies on type hinting, so use it for all function parameters, return types, and data models.
- boundaries: only operate on files in the `/backend` directory.

### Phase 1
- review mockBackend.ts, and define the exact JSON format and REST endpoints to copy

