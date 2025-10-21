"""
Prepare a minimal docker build context by copying necessary files
from the repository root into docker-context/ while excluding
unnecessary directories like `testes/`, `build/`, and other junk.

Usage:
    python scripts/prepare_docker_context.py --source . --dest docker-context

This script is safe on Windows and will copy file metadata minimally.
"""
import argparse
import shutil
import os
from pathlib import Path

EXCLUDE_DIRS = {
    'testes',
    'tests',
    'build',
    'dist',
    '__pycache__',
    '.git',
    '.venv',
    'venv',
    'tmp_uploads',
    'client',
}

EXCLUDE_FILES = {
    'requirements.txt',
}


def should_exclude(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    parts = rel.parts
    # exclude if any top-level part matches
    if parts and parts[0] in EXCLUDE_DIRS:
        return True
    # exclude if filename matches
    if path.name in EXCLUDE_FILES:
        return True
    return False


def copy_context(src: Path, dest: Path):
    if dest.exists():
        print(f"Removing existing {dest}")
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    for item in src.iterdir():
        if should_exclude(item, src):
            print(f"Skipping {item}")
            continue
        # always skip the docker-context itself
        if item.name == dest.name:
            continue
        target = dest / item.name
        if item.is_dir():
            print(f"Copying dir {item} -> {target}")
            shutil.copytree(item, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'testes', 'tests', 'build', 'dist'))
        else:
            print(f"Copying file {item} -> {target}")
            shutil.copy2(item, target)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', '-s', default='.', help='Repository root to copy from')
    parser.add_argument('--dest', '-d', default='docker-context', help='Destination folder for the docker build context')
    args = parser.parse_args()

    src = Path(args.source).resolve()
    dest = Path(args.dest).resolve()

    if not src.exists():
        print(f"Source {src} does not exist")
        return

    copy_context(src, dest)
    print(f"Docker context prepared at: {dest}")


if __name__ == '__main__':
    main()
