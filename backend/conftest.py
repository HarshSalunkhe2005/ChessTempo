import sys
from pathlib import Path

# So `import app...` resolves regardless of which directory pytest is
# invoked from — backend/ isn't a package itself (no __init__.py), just
# the parent of the `app` package.
sys.path.insert(0, str(Path(__file__).resolve().parent))
