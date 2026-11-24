import subprocess, sys
from pathlib import Path

scripts = ['activity_2_1_server_info.py', 'activity_2_1_try_yourself.py', 'activity_2_2_update_books.py', 'activity_2_2_try_yourself.py']
for script in scripts:
    print("\n" + "=" * 72)
    print("RUNNING:", script)
    print("=" * 72)
    result = subprocess.run([sys.executable, str(Path(__file__).parent / script)])
    if result.returncode != 0:
        print("Stopped because", script, "returned", result.returncode)
        sys.exit(result.returncode)
print("\nExercise 2 completed.")
