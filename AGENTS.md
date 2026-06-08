# AGENTS.md

This file defines project-specific instructions for Codex agents working in this repository.

## Project Context

This repository is a Python machine vision prototype using PyQt5, OpenCV, serial communication, and a vendored Ultralytics YOLO source tree.

The current application entry point is `gp_main.py`. Runtime behavior is split across:

- `gp_mainwindow.py` for the main window layout
- `gp_cameradisplaywidget.py` for camera capture and raw frame display
- `gp_detectionworker.py` for YOLO inference
- `gp_detectiondisplaywidget.py` for result display and serial-trigger logic
- `gp_globals.py` for current shared global state
- `gp_serial.py` for serial communication

`new1` and `aicode.py` are prototype or historical UI scripts unless the user says otherwise.

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
python -m py_compile gp_main.py gp_mainwindow.py gp_cameradisplaywidget.py gp_detectiondisplaywidget.py gp_detectionworker.py gp_globals.py gp_serial.py
```

If validation cannot run because dependencies, hardware, or display access are missing, state that clearly in the final response.

## Repository Hygiene

- Keep generated caches out of commits.
- Do not commit `.venv/`, `__pycache__/`, `.env`, logs, or local editor files.
- Use Git LFS for large model artifacts if the repository is initialized with LFS.
- Before publishing publicly, confirm whether vendoring `ultralytics/` is intentional and compatible with the chosen license.
