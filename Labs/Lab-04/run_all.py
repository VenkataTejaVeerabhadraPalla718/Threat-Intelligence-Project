import subprocess, sys
from pathlib import Path

scripts = ['activity_4_1_product_queries.py', 'activity_4_1_try_yourself.py', 'activity_4_2_upsert_bulk.py', 'activity_4_2_try_yourself.py']
for script in scripts:
    print("\n" + "=" * 72)
    print("RUNNING:", script)
    print("=" * 72)
    result = subprocess.run([sys.executable, str(Path(__file__).parent / script)])
    if result.returncode != 0:
        print("Stopped because", script, "returned", result.returncode)
        sys.exit(result.returncode)
print("\nExercise 4 completed.")
