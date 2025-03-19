# llmdirtree

A directory tree generator and codebase context provider designed specifically for enhancing LLM interactions with your code.

## Purpose

`llmdirtree` helps you work more effectively with Large Language Models (LLMs) by:
- Generating visual directory trees for structural understanding
- Creating contextual summaries of your codebase that respect privacy settings
- Optimizing code information for LLM follow-up questions

## Installation

```bash
pip install llmdirtree
```

## Key Features

### Directory Tree Visualization
- Clean, standardized visualization of project structure
- Unicode box-drawing characters for optimal parsing
- Intelligent filtering of non-essential directories

### LLM Context Generation
- AI-powered analysis of your codebase using OpenAI API
- Security-focused with automatic `.gitignore` pattern recognition
- File-by-file summaries optimized for follow-up questions
- Project overview that captures your codebase's essence

### Security and Privacy
- Respects `.gitignore` patterns to avoid exposing sensitive information
- Zero dependencies approach (uses system curl instead of libraries)
- Efficient token usage for minimal data exposure

## Usage Examples

### Basic Directory Tree

```bash
# Generate a simple directory tree
llmdirtree --root /path/to/project --output project_structure.txt
```

### With LLM Context Generation

```bash
# Generate both directory tree AND code context
llmdirtree --root /path/to/project --llm-context --openai-key YOUR_API_KEY
```

This creates two files:
- `directory_tree.txt` - Visual structure
- `llmcontext.txt` - AI-generated project overview and file summaries

### Additional Options

```bash
# Exclude specific directories
llmdirtree --exclude node_modules .git venv dist

# Customize output locations
llmdirtree --output custom_tree.txt --context-output custom_context.txt

# Control file selection for context generation
llmdirtree --max-files 150 --llm-context

# Override gitignore protection (not recommended)
llmdirtree --ignore-gitignore --llm-context
```

## Example Output

### Directory Tree

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

### LLM Context File

```markdown
# project-name

> A React web application for tracking personal fitness goals with a Node.js backend and MongoDB database.

## src/components/

- **Dashboard.jsx**: Main dashboard component that displays user fitness stats, recent activities, and goal progress.
- **WorkoutForm.jsx**: Form for creating and editing workout entries with validation and submission handling.

## src/utils/

- **api.js**: Contains functions for making API calls to the backend, handling authentication and data fetching.
- **formatters.js**: Utility functions for formatting dates, weights, and other fitness metrics consistently.
```

## Benefits for LLM Workflows

- **Comprehensive context** without uploading your entire codebase
- **More accurate responses** with both structural and semantic understanding
- **Security first** approach that protects sensitive information
- **Time savings** from clearer communication with AI assistants

## Technical Details

- No external dependencies required for core functionality
- Progress bar available with optional `tqdm` installation
- Automatically respects `.gitignore` patterns for security
- Uses system curl instead of Python libraries for API calls

## License

MIT
