from pathlib import Path
import sys


def ensure_repo_root(path: Path | str | None = None) -> Path:
    """Ensure the repository root is on sys.path and return the resolved root."""
    if path is None:
        path = Path(__file__).resolve().parent
    else:
        path = Path(path)

    repo_root = path.resolve()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    return repo_root
