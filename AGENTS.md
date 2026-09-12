# AGENTS.md

This file defines project-specific instructions for Codex agents working in this repository.

## Project Context

This repository is GearPro, a Python machine vision app using PyQt5, OpenCV,
serial communication, and a vendored Ultralytics YOLO source tree.

Develop on branch `srtp`. `main` is the published app; `archive-old` is the
pre-refactor tree. Do not add features on `archive-old`.

EdgeMedic (bounded autonomy around GearPro) is specified in `docs/edgemedic.md`
and `.cursor/rules/edgemedic.mdc`. Implement telemetry and control APIs before
any LLM reasoner. Do not add ROS/LiDAR. Do not claim unimplemented V5 modes.

The current application entry point is `gp_main.py` (or `python -m gp`).
Runtime behavior lives in `gp/`:

- `gp/app.py` for Qt startup
- `gp/ui.py` for the main window and settings
- `gp/camera.py` for capture and the latest-frame buffer
- `gp/worker.py` for background inference
- `gp/models.py` for the two-stage YOLO + Scratch V5 pipeline
- `gp/scratch_v5.py` for fusion runtime
- `gp/serial_io.py` for serial output
- `gp/config.py` and `gp/types.py` for settings and result objects
- `gp/actions.py`, `gp/control.py`, and `gp/guardian.py` for Control API and in-process L0
- `edgemedic/` is a **separate process** (`python -m edgemedic`) talking HTTP only

Old `gp_*.py` scripts, `new1`, and `aicode.py` live under `legacy/` unless
the user says otherwise. Jetson NX checkout: `/home/jetson/Projects/Machine_vision`
(branch `srtp`); the previous NX tree is `/home/jetson/archive/Machine_vision-old-2026-09-12`.

## Work Rules

- Keep changes tightly scoped to the user's request.
- Do not rewrite or reorganize the project unless explicitly requested.
- Prefer the existing PyQt5/OpenCV style while the project is being refactored incrementally.
- Do not remove model files, prototype scripts, or the vendored `ultralytics/` tree without explicit approval.
- Do not change hardware defaults such as camera index, serial port, baud rate, confidence threshold, or model path unless the task is specifically about configuration or portability.
- Avoid unrelated formatting churn.
- Preserve Chinese UI text unless the user requests localization changes.

## Python Guidance

- Use straightforward Python modules and functions.
- Avoid adding new frameworks unless the user asks for them.
- Keep comments concise and useful.
- When changing runtime code, check for import errors or syntax errors with `py_compile` when feasible.
- Be careful with PyQt thread ownership. Prefer small, compatible fixes over broad thread-model rewrites unless the task is explicitly a refactor.

## Git And Commits

The user wants Codex to handle commits for this project.

When asked to commit, or when a task reaches a natural commit point:

1. Inspect `git status --short`.
2. Inspect the relevant diff.
3. Do not include unrelated user changes unless explicitly asked.
4. Run lightweight validation when feasible.
5. Commit using `COMMIT_CONVENTION.md`.
6. Report the commit hash and the main files changed.

Commit messages must follow:

```text
<type>(<scope>): <summary>
```

Examples:

```text
docs(repo): add GitHub publishing guide
fix(detection): apply detection interval setting
refactor(config): isolate runtime defaults
```

Do not use vague messages such as `update`, `fix`, `wip`, or `changes`.

## Validation Defaults

For documentation-only changes:

```bash
git diff --check
```

For Python code changes:

```bash
python -m py_compile gp_main.py run_pt.py run_engine.py export_engine.py gp/app.py gp/actions.py gp/camera.py gp/config.py gp/control.py gp/export_engine.py gp/frames.py gp/guardian.py gp/launch.py gp/models.py gp/profiles.py gp/serial_io.py gp/telemetry.py gp/types.py gp/ui.py gp/worker.py gp/weights.py edgemedic/__init__.py edgemedic/__main__.py edgemedic/client.py edgemedic/memory.py edgemedic/policy.py edgemedic/reasoner.py edgemedic/runtime.py
python -m unittest discover -s tests -v
```

If validation cannot run because dependencies, hardware, or display access are missing, state that clearly in the final response.

## Repository Hygiene

- Keep generated caches out of commits.
- Do not commit `.venv/`, `__pycache__/`, `.env`, logs, or local editor files.
- Use Git LFS for large model artifacts if the repository is initialized with LFS.
- Before publishing publicly, confirm whether vendoring `ultralytics/` is intentional and compatible with the chosen license.
