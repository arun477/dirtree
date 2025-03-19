# llmdirtree

A simple, customizable directory tree generator CLI tool that creates text-based visualizations of your file system structure.

## Installation

```bash
pip install llmdirtree
```

## Usage

```bash
# Basic usage (current directory)
llmdirtree

# Specify root directory
llmdirtree --root /path/to/directory

# Exclude specific directories
llmdirtree --exclude node_modules .git build

# Custom output file
llmdirtree --output myproject_structure.txt
```

## Features

- Clean visualization of directory hierarchies
- Customizable exclusion patterns
- Works on any OS (Windows, macOS, Linux)
- Handles permission errors gracefully

## Example Output

```
Directory Tree for: /path/to/project
Excluding: .git, __pycache__, node_modules, venv
--------------------------------------------------
project/
├── src/
│   ├── main.py
│   └── utils/
│       ├── helpers.py
│       └── config.py
├── tests/
│   ├── test_main.py
│   └── test_utils.py
├── README.md
└── setup.py
```

## License

MIT

## Contributing

Contributions welcome! Feel free to submit issues or pull requests.
