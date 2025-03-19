import os
import argparse
from typing import Set, TextIO

def write_directory_tree(file: TextIO, root_dir: str, exclude_dirs: Set[str], prefix: str = ""):
    """
    Write a directory tree structure to a file, excluding specified directories.
    """
    try:
        # Get items in the directory, excluding those in exclude_dirs
        items = []
        for item in sorted(os.listdir(root_dir)):
            if item in exclude_dirs:
                continue
            
            path = os.path.join(root_dir, item)
            is_dir = os.path.isdir(path)
            items.append((item, path, is_dir))
    except PermissionError:
        file.write(f"{prefix}[Permission Denied]\n")
        return
    except FileNotFoundError:
        file.write(f"{prefix}[Directory Not Found]\n")
        return
    
    # Process each item
    for i, (item, path, is_dir) in enumerate(items):
        is_last = i == len(items) - 1
        
        # Write the item with appropriate connectors
        connector = "└── " if is_last else "├── "
        file.write(f"{prefix}{connector}{item}" + ("/" if is_dir else "") + "\n")
        
        # If it's a directory, recursively write its contents
        if is_dir:
            # Set the prefix for the next level
            next_prefix = prefix + ("    " if is_last else "│   ")
            write_directory_tree(file, path, exclude_dirs, next_prefix)

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Generate a directory tree structure")
    parser.add_argument("--root", default=".", help="Root directory to start from (default: current directory)")
    parser.add_argument("--exclude", nargs="+", default=["node_modules", "__pycache__", ".git", "venv"], 
                        help="Directories to exclude (default: node_modules, __pycache__, .git, venv)")
    parser.add_argument("--output", default="directory_tree.txt", 
                        help="Output file name (default: directory_tree.txt)")
    args = parser.parse_args()
    
    # Convert exclude_dirs to a set for O(1) lookups
    exclude_dirs = set(args.exclude)
    
    # Determine absolute path for root directory
    root_dir = os.path.abspath(args.root)
    
    # Get the directory name
    dir_name = os.path.basename(root_dir)
    if not dir_name:  # Handle case of root directory
        dir_name = root_dir
    
    # Write the tree to the specified file
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(f"Directory Tree for: {root_dir}\n")
        f.write(f"Excluding: {', '.join(sorted(exclude_dirs))}\n")
        f.write("-" * 50 + "\n")
        f.write(f"{dir_name}/\n")
        write_directory_tree(f, root_dir, exclude_dirs)
    
    print(f"Directory tree has been saved to: {args.output}")

if __name__ == "__main__":
    main()