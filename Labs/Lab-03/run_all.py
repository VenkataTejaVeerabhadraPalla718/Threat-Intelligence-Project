import subprocess, sys
from pathlib import Path

scripts = ['activity_3_1_embedded_schema.py', 'activity_3_1_try_yourself.py', 'activity_3_2_blog_migration.py', 'activity_3_2_try_yourself.py']
for script in scripts:
    print("\n" + "=" * 72)
    print("RUNNING:", script)
    print("=" * 72)
    result = subprocess.run([sys.executable, str(Path(__file__).parent / script)])
    if result.returncode != 0:
        print("Stopped because", script, "returned", result.returncode)
        sys.exit(result.returncode)
print("\nExercise 3 completed.")
