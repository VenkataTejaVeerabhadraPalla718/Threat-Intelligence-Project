import subprocess, sys
from pathlib import Path

scripts = ['activity_1_1_classify_products.py', 'activity_1_1_try_yourself.py', 'activity_1_2_application_mapping.py', 'activity_1_2_try_yourself.py']
for script in scripts:
    print("\n" + "=" * 72)
    print("RUNNING:", script)
    print("=" * 72)
    result = subprocess.run([sys.executable, str(Path(__file__).parent / script)])
    if result.returncode != 0:
        print("Stopped because", script, "returned", result.returncode)
        sys.exit(result.returncode)
print("\nExercise 1 completed.")
