import os
import fnmatch


def show_tree(directory, prefix="", ignore_patterns=None, max_depth=5, current_depth=0):
    if ignore_patterns is None:
        ignore_patterns = ['__pycache__', '*.pyc', '.git', 'venv', 'env', '.idea', 'node_modules']

    if current_depth >= max_depth:
        return

    try:
        entries = sorted(os.listdir(directory))
    except PermissionError:
        return

    dirs = [e for e in entries if os.path.isdir(os.path.join(directory, e))]
    files = [e for e in entries if os.path.isfile(os.path.join(directory, e))]

    # Filter out ignored patterns
    dirs = [d for d in dirs if not any(fnmatch.fnmatch(d, pattern) for pattern in ignore_patterns)]
    files = [f for f in files if not any(fnmatch.fnmatch(f, pattern) for pattern in ignore_patterns)]

    all_entries = dirs + files

    for i, entry in enumerate(all_entries):
        is_last = i == len(all_entries) - 1
        current_prefix = "└── " if is_last else "├── "
        print(f"{prefix}{current_prefix}{entry}")

        entry_path = os.path.join(directory, entry)
        if os.path.isdir(entry_path):
            extension = "    " if is_last else "│   "
            show_tree(entry_path, prefix + extension, ignore_patterns, max_depth, current_depth + 1)


print("Project Structure:")
print(".")
show_tree(".", max_depth=4)
