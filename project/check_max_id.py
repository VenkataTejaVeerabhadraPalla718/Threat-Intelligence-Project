import sys
from pathlib import Path

# Force Python to look in the project root directory first
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Now this will work because 'sentinelx' is a local folder in the path
from sentinelx.common import db
