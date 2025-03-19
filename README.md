# llmdirtree

A specialized directory tree generator designed for LLMs to understand project structures and file organization.

## Purpose

`llmdirtree` creates standardized text representations of directory structures that are optimized for:
- Large Language Models (LLMs) to process and understand code repositories
- AI assistants working with codebases
- Consistent directory visualization in LLM prompts

## Installation

```bash
pip install llmdirtree
```

## Usage with LLMs

### Basic Workflow

1. Generate a directory tree:
   ```bash
   llmdirtree --root /path/to/project --output project_structure.txt
   ```

2. Include the structure in your LLM prompt:
   ```
   Here's my project structure:
   ```
   [paste content of project_structure.txt]
   ```
   Can you help me understand...
   ```

### CLI Options

```bash
# Default usage
llmdirtree

# Specify root directory
llmdirtree --root /path/to/codebase

# Exclude irrelevant directories
llmdirtree --exclude node_modules .git venv

# Custom output location
llmdirtree --output project_context.txt
```

## Output Format

Output is formatted with Unicode box-drawing characters for optimal parsing:

```
Directory Tree for: /project
Excluding: .git, node_modules, __pycache__, venv
--------------------------------------------------
project/
├── src/
│   ├── main.py
│   └── utils/
│       └── helpers.py
├── tests/
│   └── test_main.py
└── README.md
```

## Benefits for LLM Workflows

- **Contextual Understanding**: Helps LLMs understand project organization at a glance
- **Focused Analysis**: Excludes non-essential directories by default
- **Consistent Format**: Standardized output format is easily parsed by AI models
- **Memory Efficient**: Provides high-level context without requiring full codebase upload

## License

MIT
