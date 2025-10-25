#!/usr/bin/env python3
"""
utils/generate_structure_txt.py
VERSION: 1.0
PURPOSE: Generate visual tree structure of project files
USAGE: python utils/generate_structure_txt.py
"""

from pathlib import Path


def get_tree_structure(directory, prefix="", ignore_dirs=None, ignore_files=None):
    """
    Generate tree structure of directory.

    Args:
        directory: Root directory path
        prefix: Prefix for tree lines
        ignore_dirs: Set of directory names to ignore
        ignore_files: Set of file names to ignore

    Returns:
        List of strings representing tree structure
    """
    if ignore_dirs is None:
        ignore_dirs = {
            "__pycache__",
            ".git",
            ".idea",
            ".vscode",
            "venv",
            "env",
            ".pytest_cache",
            ".mypy_cache",
            "node_modules",
            "dist",
            "build",
        }

    if ignore_files is None:
        ignore_files = {
            ".DS_Store",
            "Thumbs.db",
            ".gitignore",
            "*.pyc",
            "*.pyo",
            "*.pyd",
        }

    lines = []
    path = Path(directory)

    if not path.exists():
        return [f"❌ Directory not found: {directory}"]

    # Get all items in directory
    try:
        items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
    except PermissionError:
        return [f"{prefix}❌ Permission denied"]

    # Separate directories and files
    dirs = [item for item in items if item.is_dir() and item.name not in ignore_dirs]
    files = [item for item in items if item.is_file() and item.name not in ignore_files]

    all_items = dirs + files

    for i, item in enumerate(all_items):
        is_last = i == len(all_items) - 1

        # Draw tree lines
        if is_last:
            current_prefix = "└── "
            next_prefix = "    "
        else:
            current_prefix = "├── "
            next_prefix = "│   "

        # Add current item
        if item.is_dir():
            lines.append(f"{prefix}{current_prefix}{item.name}/")
            # Recurse into directory (max depth 3)
            if prefix.count("│") < 2:  # Limit depth
                sub_lines = get_tree_structure(
                    item, prefix + next_prefix, ignore_dirs, ignore_files
                )
                lines.extend(sub_lines)
        else:
            lines.append(f"{prefix}{current_prefix}{item.name}")

    return lines


def main():
    """Main function to generate and print project structure."""

    # Get project root (parent of utils/)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    print("=" * 80)
    print(f"PROJECT STRUCTURE: {project_root.name}")
    print("=" * 80)
    print()

    # Generate tree
    tree = get_tree_structure(project_root)

    # Print tree
    print(f"{project_root.name}/")
    for line in tree:
        print(line)

    print()
    print("=" * 80)
    print(f"Total lines: {len(tree)}")
    print("=" * 80)

    # Save to file
    output_file = project_root / "project_structure.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"{project_root.name}/\n")
        for line in tree:
            f.write(line + "\n")

    print(f"\n✅ Structure saved to: {output_file}")


if __name__ == "__main__":
    main()
