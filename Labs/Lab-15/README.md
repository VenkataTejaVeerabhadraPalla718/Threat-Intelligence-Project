# Lab-15 — Detailed Lab Guide

> Generated from the files present in this lab folder. Verify the exact aim, dataset, entry point and expected output against the official lab sheet.

## 1. Aim and objectives

**Aim:** Replace this line with the exact aim from the official exercise sheet.

- Understand the concepts implemented in this exercise.
- Configure and execute the required tools.
- Verify the result against the official expected output.

## 2. Previous README notes

# NoSQL Lab 15

## Objective
Refer to the experiment files and implementation included in this folder.

## Contents
This folder contains the source files, scripts, configurations and supporting materials for Lab 15.

## Execution
1. Open this folder in Visual Studio Code.
2. Review the experiment files.
3. Follow the instructions in the included files.
4. Execute the experiment using the required MongoDB environment.

## Technologies
- MongoDB
- NoSQL
- Python / JavaScript / Docker (where applicable)

## Author
Venkata Teja Veerabhadra Palla

USN: 24BTLCL006

## 3. Technologies detected

- Python

## 4. File inventory

- `01_seed.py`
- `02_test_api.py`
- `03_migrate.py`

## 5. Prerequisites and setup

- Windows PowerShell.
- Install the runtime indicated by the detected source files (Python, Java, Node.js, Docker, etc.).
- For Python, use a virtual environment and install the dependencies listed in this lab.
- For MongoDB exercises, start the MongoDB service/container and use the URI configured by the lab.
- Never put passwords, tokens, private keys or .env contents in this README.

## 6. Execution commands

Run from PowerShell. These are safe starting commands inferred from files; select the correct application entry point from the lab source/instructions.

```powershell
Set-Location "V:\NoSQL\SENTINELX-LOCAL\github-upload\Labs\Lab-15"
# Python files detected: 01_seed.py, 03_migrate.py
# Check the lab instructions/source to choose the intended entry point; do not run every file.
```

## 7. Expected output and verification

- Record the actual terminal/notebook/database output produced by this lab.
- Compare output with the official lab sheet; this README generator does not invent results.
- Add screenshots and explain what each output demonstrates.

## 8. Troubleshooting

| Issue | Check |
|---|---|
| Command not found | Confirm runtime installation and PATH. |
| Python module missing | Activate the correct venv and install requirements. |
| MongoDB connection refused | Check service/container, host, port and URI. |
| Docker unavailable | Start Docker Desktop and wait for engine readiness. |
| Port conflict | Identify the process using the port before changing configuration. |
| Authentication failure | Check local credentials; never publish them. |

## 9. Cleanup and data safety

- Stop only the processes/containers started for this lab.
- Preserve database volumes and datasets unless a reset is explicitly required.
- Avoid docker compose down -v, docker volume prune and destructive database commands for routine cleanup.

## 10. Completion checklist

- [ ] Aim/objectives match the official lab sheet.
- [ ] Tool versions and prerequisites are recorded.
- [ ] Commands have been tested.
- [ ] Actual outputs/screenshots are included.
- [ ] No credentials or private data are committed.
