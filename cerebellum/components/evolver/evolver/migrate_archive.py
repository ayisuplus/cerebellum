"""Check for existing SQLite archive data and provide migration guidance.

Evolver's dead-data layer is MySQL-only. This script scans common locations
for legacy SQLite archive databases and prints migration steps when found.
"""

import os
import sys
from pathlib import Path


def _candidate_paths() -> list[str]:
    """Return candidate paths to check for legacy SQLite archive data."""
    package_dir = Path(__file__).resolve().parent
    cwd = Path.cwd()
    home = Path.home()

    candidates = [
        cwd / "evolver_archive.db",
        cwd / "evolver.db",
        package_dir / "evolver_archive.db",
        home / ".evolver" / "evolver_archive.db",
    ]
    return [str(p) for p in candidates]


def check_sqlite_archive() -> list[dict]:
    """Check if SQLite archive database exists in known locations.

    Returns:
        List of dicts with 'path' and 'size' (bytes) for each found file.
    """
    found: list[dict] = []
    for path in _candidate_paths():
        if os.path.exists(path):
            try:
                size = os.path.getsize(path)
            except OSError:
                size = 0
            found.append({"path": path, "size": size})
    return found


def _print_found(found: list[dict]) -> None:
    print("\n[WARNING] Found SQLite archive database(s):")
    for item in found:
        print(f"  - {item['path']} ({item['size']} bytes)")

    print()
    print("Migration steps:")
    print("  1. Backup the SQLite database:")
    print('     cp evolver_archive.db evolver_archive.db.backup')
    print('     # PowerShell: Copy-Item evolver_archive.db evolver_archive.db.backup')
    print()
    print("  2. Install MySQL (if not already installed):")
    print("     docker run -d --name mysql-evolver \\")
    print("       -e MYSQL_ROOT_PASSWORD=*** \\")
    print("       -e MYSQL_DATABASE=evolver_archive \\")
    print("       -p 3306:3306 \\")
    print("       mysql:8.0")
    print()
    print("  3. Configure EVOLVER_DATA_URL:")
    print("     Bash:       export EVOLVER_DATA_URL='mysql://root:***@localhost:3306/evolver_archive'")
    print("     PowerShell: $env:EVOLVER_DATA_URL='mysql://root:***@localhost:3306/evolver_archive'")
    print()
    print("  4. Import data (optional):")
    print("     # Use mysqldump or custom migration script")
    print()
    print("  5. Verify migration:")
    print("     evolver query-archive --query 'test'")
    print()
    print("[WARNING] SQLite archive data will NOT be automatically migrated.")
    print("          Please backup before proceeding.")


def _print_clean() -> None:
    print("\n[OK] No SQLite archive databases found.")
    print("     You can proceed with MySQL configuration.")


def main() -> int:
    """Main migration check. Returns 0 if clean, 1 if legacy data found."""
    print("=" * 60)
    print("Evolver Archive Migration Check")
    print("=" * 60)

    found = check_sqlite_archive()
    if found:
        _print_found(found)
        print()
        print("=" * 60)
        return 1
    _print_clean()
    print()
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
