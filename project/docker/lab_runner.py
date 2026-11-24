import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAB_ID = os.getenv("LAB_ID", "")

COMMANDS = {
    "lab13": {
        "observe": ("01_failover_auth.py", []),
    },
    "lab14": {
        "monitor": ("01_monitor.py", ["--once"]),
        "monitor-loop": ("01_monitor.py", []),
        "backup-verify": ("02_backup_verify.py", ["verify"]),
        "backup-benchmark": ("02_backup_verify.py", ["benchmark"]),
        "backup-hourly": ("02_backup_verify.py", ["hourly"]),
    },
    "lab15": {
        "seed": ("01_seed.py", []),
        "test": ("02_test_api.py", []),
        "migrate": ("03_migrate.py", []),
    },
    "lab16": {
        "seed": ("01_model_and_seed.py", []),
    },
    "lab17": {
        "pipeline": ("01_rag_pipeline.py", []),
        "vector": ("02_hnsw_vs_ivf.py", []),
    },
    "lab18": {
        "benchmark": ("01_benchmark.py", []),
    },
}

CONFIRMATIONS = {
    ("lab15", "seed"): "CONFIRM_LAB15_SEED",
    ("lab15", "migrate"): "CONFIRM_LAB15_MIGRATION",
    ("lab16", "seed"): "CONFIRM_LAB16_RESET",
}

REQUIRED_ENV = {
    ("lab15", "seed"): ("JWT_SECRET",),
    ("lab17", "pipeline"): ("VECTOR_MONGO_URI",),
    ("lab17", "vector"): ("VECTOR_MONGO_URI",),
}


def main():
    if LAB_ID not in COMMANDS:
        print("Invalid or missing LAB_ID image configuration.", file=sys.stderr)
        return 2

    commands = COMMANDS[LAB_ID]
    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        print(f"Usage: docker run IMAGE <{'|'.join(commands)}>")
        for name in commands:
            print(f"  {name}")
        return 0 if len(sys.argv) < 2 else 2

    action = sys.argv[1]
    confirmation = CONFIRMATIONS.get((LAB_ID, action))
    if confirmation and os.getenv(confirmation) != "1":
        print(
            f"{LAB_ID} {action} changes lab data. Set {confirmation}=1 "
            "only after confirming the data can be replaced.",
            file=sys.stderr,
        )
        return 2

    missing = [name for name in REQUIRED_ENV.get((LAB_ID, action), ()) if not os.getenv(name)]
    if missing:
        print(f"Set the required environment variable(s): {', '.join(missing)}", file=sys.stderr)
        return 2
    if action.startswith("backup-") and not Path("/var/run/docker.sock").exists():
        print(
            "Mount the host Docker socket at /var/run/docker.sock for backup commands.",
            file=sys.stderr,
        )
        return 2

    script, default_args = commands[action]
    command = [sys.executable, str(ROOT / "labs" / LAB_ID / script), *default_args, *sys.argv[2:]]
    return subprocess.run(command, cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
