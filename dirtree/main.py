#!/usr/bin/env python3
"""
llmdirtree - Directory Tree Generator and LLM Context Provider

This script generates a visual directory tree structure and optionally creates
a comprehensive context file for LLM interactions that respects .gitignore patterns.
"""

import os
import argparse
import json
import logging
import subprocess
import tempfile
import shutil
import fnmatch
import re
from typing import Set, TextIO, List, Dict, Tuple, Pattern, Optional
from pathlib import Path


def write_directory_tree(
    file: TextIO, 
    root_dir: str, 
    exclude_dirs: Set[str], 
    prefix: str = "", 
    gitignore_patterns: Optional[List[str]] = None,
    project_root: Optional[str] = None
):
    """
    Write a directory tree structure to a file, excluding specified directories
    and respecting gitignore patterns.
    """
    # Use the root_dir as project_root if not provided
    if project_root is None:
        project_root = root_dir
        
    try:
        # Get items in the directory, excluding those in exclude_dirs
        items = []
        for item in sorted(os.listdir(root_dir)):
            if item in exclude_dirs:
                continue

            path = os.path.join(root_dir, item)
            
            # Skip items ignored by gitignore
            if gitignore_patterns and is_ignored_by_gitignore(path, project_root, gitignore_patterns):
                continue
                
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
            write_directory_tree(file, path, exclude_dirs, next_prefix, gitignore_patterns, project_root)


def is_text_file(file_path: str) -> bool:
    """Determine if a file is a text file that should be analyzed."""
    # Check if file exists and is not a directory
    if not os.path.isfile(file_path):
        return False

    # Check file extension for common text file types
    text_extensions = {
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".html",
        ".css",
        ".md",
        ".txt",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".sh",
        ".bash",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".java",
        ".kt",
        ".go",
        ".rs",
        ".rb",
        ".php",
        ".swift",
    }

    ext = os.path.splitext(file_path)[1].lower()
    if ext in text_extensions:
        return True

    # Try to read the file as text as a last resort
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            f.read(1024)  # Try to read a small chunk
        return True
    except UnicodeDecodeError:
        return False


def estimate_tokens(text: str) -> int:
    """Estimate number of tokens in text using a simple approximation."""
    # Simple approximation: ~4 chars per token for English text
    return len(text) // 4


def parse_gitignore(gitignore_path: str) -> List[str]:
    """Parse a .gitignore file and return a list of patterns."""
    patterns = []

    try:
        with open(gitignore_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue
                patterns.append(line)
    except Exception as e:
        logging.warning(f"Error reading .gitignore file: {e}")

    return patterns


def convert_gitignore_pattern_to_regex(pattern: str) -> str:
    """
    Convert a gitignore pattern to a regex pattern.

    Handles special gitignore pattern features:
    * - matches any string except path separator
    ** - matches any string including path separator
    ? - matches a single character except path separator
    [abc] - matches characters in brackets
    ! - negates a pattern
    """
    if not pattern:
        return ""

    # Handle directory-only pattern (trailing slash)
    dir_only = False
    if pattern.endswith("/"):
        dir_only = True
        pattern = pattern[:-1]

    # Escape special regex characters but keep gitignore wildcards
    escaped = ""
    i = 0
    while i < len(pattern):
        # Handle ** wildcard (matches across directories)
        if i + 1 < len(pattern) and pattern[i : i + 2] == "**":
            escaped += ".*"
            i += 2
        # Handle * wildcard (doesn't match directory separator)
        elif pattern[i] == "*":
            escaped += "[^/]*"
            i += 1
        # Handle ? wildcard (single character, but not directory separator)
        elif pattern[i] == "?":
            escaped += "[^/]"
            i += 1
        # Handle character classes [abc]
        elif pattern[i] == "[":
            end_bracket = pattern.find("]", i)
            if end_bracket != -1:
                escaped += pattern[i : end_bracket + 1]
                i = end_bracket + 1
            else:
                escaped += "\\["
                i += 1
        # Escape regex special characters
        elif pattern[i] in ".+(){}^$|\\":
            escaped += "\\" + pattern[i]
            i += 1
        else:
            escaped += pattern[i]
            i += 1

    # If it's a directory pattern, it should match the directory and all its contents
    if dir_only:
        return f"^{escaped}(/.*)?$"
    else:
        return f"^{escaped}$"


def is_ignored_by_gitignore(
    file_path: str, root_dir: str, gitignore_patterns: List[str]
) -> bool:
    """
    Check if a file should be ignored based on gitignore patterns.

    Args:
        file_path: Absolute path to the file
        root_dir: Root directory of the project
        gitignore_patterns: List of patterns from .gitignore

    Returns:
        True if the file should be ignored, False otherwise
    """
    if not gitignore_patterns:
        return False

    # Get the relative path from the root directory
    rel_path = os.path.relpath(file_path, root_dir)
    # Use forward slashes for consistency (gitignore standard)
    rel_path = rel_path.replace(os.path.sep, "/")

    # Check each directory level for matches
    path_parts = rel_path.split("/")
    paths_to_check = [rel_path]

    # Also check if any parent directory matches a pattern
    for i in range(1, len(path_parts)):
        paths_to_check.append("/".join(path_parts[:i]))

    # Track matched patterns (last matching pattern wins)
    should_ignore = False

    # Check all patterns (last match wins)
    for pattern in gitignore_patterns:
        # Skip empty patterns
        if not pattern:
            continue

        # Handle negated patterns
        negated = pattern.startswith("!")
        if negated:
            pattern = pattern[1:]

        # Skip patterns that start with # (comments)
        if pattern.startswith("#"):
            continue

        # Convert pattern to regex if it has wildcards
        if any(c in pattern for c in "*?["):
            pattern_regex = convert_gitignore_pattern_to_regex(pattern)

            # Check if any path level matches the pattern
            for path in paths_to_check:
                if re.match(pattern_regex, path):
                    should_ignore = not negated
                    break

        # Simple exact match (handles patterns without wildcards)
        elif any(
            path == pattern or path.startswith(pattern + "/") for path in paths_to_check
        ):
            should_ignore = not negated

    return should_ignore


def collect_files_for_context(
    root_dir: str,
    exclude_dirs: Set[str],
    max_files: int = 100,
    max_size_kb: int = 100,
    max_total_tokens: int = 100000,
    respect_gitignore: bool = True,
) -> List[Tuple[str, str, int]]:
    """
    Collect text files for context generation with size and token limits.
    Returns list of (file_path, relative_path, token_count) tuples.
    """
    collected_files = []
    total_tokens = 0

    # Check for .gitignore file and parse patterns
    gitignore_path = os.path.join(root_dir, ".gitignore")
    gitignore_patterns = []
    if respect_gitignore and os.path.isfile(gitignore_path):
        gitignore_patterns = parse_gitignore(gitignore_path)
        print(
            f"Found .gitignore with {len(gitignore_patterns)} patterns - will respect these patterns"
        )

    for root, dirs, files in os.walk(root_dir):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        # Skip directories ignored by gitignore
        if respect_gitignore and gitignore_patterns:
            dirs[:] = [d for d in dirs if not is_ignored_by_gitignore(
                os.path.join(root, d), root_dir, gitignore_patterns)]

        for file in sorted(files):
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, root_dir)

            # Skip files larger than max_size_kb
            file_size_kb = os.path.getsize(file_path) / 1024
            
            # Only process text files
            if not is_text_file(file_path):
                continue

            # Skip files ignored by .gitignore
            if gitignore_patterns and is_ignored_by_gitignore(
                file_path, root_dir, gitignore_patterns
            ):
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                token_count = estimate_tokens(content)

                # Skip files that would exceed our token budget
                if total_tokens + token_count > max_total_tokens:
                    continue

                collected_files.append((file_path, relative_path, token_count))
                total_tokens += token_count

                # Stop if we've reached our file limit
                if len(collected_files) >= max_files:
                    break
            except Exception as e:
                logging.warning(f"Error reading {file_path}: {e}")

        # Stop if we've reached our file limit
        if len(collected_files) >= max_files:
            break

    return collected_files


def split_file_into_chunks(content: str, max_tokens_per_chunk: int = 4000) -> List[str]:
    """
    Split file content into chunks that don't exceed the token limit.
    Tries to split at natural boundaries like newlines.
    """
    # If content is small enough, return it as is
    if estimate_tokens(content) <= max_tokens_per_chunk:
        return [content]
    
    chunks = []
    lines = content.split('\n')
    current_chunk = []
    current_tokens = 0
    
    for line in lines:
        line_tokens = estimate_tokens(line + '\n')
        
        # If a single line exceeds the token limit, split it further
        if line_tokens > max_tokens_per_chunk:
            # If we have content in the current chunk, add it first
            if current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = []
                current_tokens = 0
            
            # Split long line into smaller pieces
            words = line.split(' ')
            sub_line = []
            sub_tokens = 0
            
            for word in words:
                word_tokens = estimate_tokens(word + ' ')
                if sub_tokens + word_tokens > max_tokens_per_chunk:
                    if sub_line:  # Add accumulated sub_line to chunks
                        chunks.append(' '.join(sub_line))
                    sub_line = [word]
                    sub_tokens = word_tokens
                else:
                    sub_line.append(word)
                    sub_tokens += word_tokens
            
            # Add any remaining part of the line
            if sub_line:
                current_chunk.append(' '.join(sub_line))
                current_tokens = estimate_tokens(' '.join(sub_line) + '\n')
                
        # If adding this line would exceed the limit, start a new chunk
        elif current_tokens + line_tokens > max_tokens_per_chunk:
            chunks.append('\n'.join(current_chunk))
            current_chunk = [line]
            current_tokens = line_tokens
        else:
            current_chunk.append(line)
            current_tokens += line_tokens
    
    # Add the last chunk if it has content
    if current_chunk:
        chunks.append('\n'.join(current_chunk))
    
    return chunks


def ask_for_model_preference(default_model: str) -> str:
    """
    Ask the user if they want to use the default model or specify a different one.
    Returns the model name to use.
    """
    response = input(f"Would you like to use the default model ({default_model}) for all API calls? [Y/n]: ").strip().lower()
    if response == "" or response.startswith("y"):
        print(f"Using default model: {default_model}")
        return default_model
    
    # User wants to specify a different model
    custom_model = input("Please enter the OpenAI model you would like to use: ").strip()
    if custom_model:
        print(f"Using model: {custom_model} for all API calls")
        return custom_model
    else:
        print(f"No model specified, using default: {default_model}")
        return default_model


def call_openai_api(
    prompt: str, api_key: str, model: str = "gpt-3.5-turbo", max_tokens: int = 1000
) -> str:
    """Call OpenAI API using curl command."""

    # Create JSON payload
    data = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant that provides concise code and document summaries for developers.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": max_tokens,
    }

    # Write JSON to a temporary file
    fd, temp_path = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)

        # Prepare curl command
        curl_cmd = [
            "curl",
            "https://api.openai.com/v1/chat/completions",
            "-H",
            f"Authorization: Bearer {api_key}",
            "-H",
            "Content-Type: application/json",
            "-d",
            f"@{temp_path}",
        ]

        # Execute curl command
        result = subprocess.run(curl_cmd, capture_output=True, text=True, check=True)

        # Parse the JSON response
        try:
            response = json.loads(result.stdout)
            if "choices" in response and len(response["choices"]) > 0:
                return response["choices"][0]["message"]["content"].strip()
            else:
                logging.error(f"Unexpected API response format: {result.stdout}")
                return ""
        except json.JSONDecodeError:
            logging.error(f"Failed to parse API response: {result.stdout}")
            return ""

    except subprocess.CalledProcessError as e:
        logging.error(f"API call failed: {e.stderr}")
        return ""
    finally:
        # Always clean up the temp file
        os.unlink(temp_path)


def generate_summary_for_large_file(
    file_path: str, relative_path: str, content: str, api_key: str, 
    max_tokens_per_chunk: int = 4000, model: str = "gpt-3.5-turbo"
) -> str:
    """
    Generate a summary for a large file by splitting it into chunks,
    summarizing each chunk, and then summarizing the combined summaries.
    """
    print(f"Handling large file: {relative_path}")
    
    # Split the file into chunks
    chunks = split_file_into_chunks(content, max_tokens_per_chunk)
    chunk_summaries = []
    
    print(f"  - Split into {len(chunks)} chunks")
    
    # Summarize each chunk
    for i, chunk in enumerate(chunks):
        chunk_prompt = f"Summarize this code chunk ({i+1}/{len(chunks)}) from file '{relative_path}'. Focus on:\n"
        chunk_prompt += "1. What functionality this particular chunk implements\n"
        chunk_prompt += "2. How it fits into the larger file (if apparent)\n"
        chunk_prompt += "3. Key data structures or algorithms used\n\n"
        chunk_prompt += "Be concise (2-3 sentences max).\n\n"
        chunk_prompt += f"CODE CHUNK:\n{chunk}"
        
        chunk_summary = call_openai_api(
            chunk_prompt, api_key, model=model, max_tokens=200
        )
        if chunk_summary:
            chunk_summaries.append(chunk_summary)
    
    # If we only have one chunk summary, return it
    if len(chunk_summaries) == 1:
        return chunk_summaries[0]
    
    # Otherwise, summarize the summaries
    combined_prompt = "Create a unified summary of this file based on summaries of its chunks:\n\n"
    combined_prompt += f"FILE: {relative_path}\n\n"
    combined_prompt += "CHUNK SUMMARIES:\n"
    
    # Add each chunk summary
    for i, summary in enumerate(chunk_summaries):
        combined_prompt += f"Chunk {i+1}: {summary}\n\n"
    
    combined_prompt += "Provide a final, coherent summary of the entire file's purpose and functionality (3-4 sentences max)."
    
    final_summary = call_openai_api(
        combined_prompt, api_key, model=model, max_tokens=250
    )
    
    return final_summary or "A large file with multiple components."


def generate_file_summaries(
    files: List[Tuple[str, str, int]], api_key: str, batch_size: int = 5, model: str = "gpt-3.5-turbo-16k"
) -> Dict[str, str]:
    """
    Generate summaries for files using OpenAI API via curl.
    Process files in batches to be efficient.
    Handle large files by splitting them into chunks.
    """
    summaries = {}
    max_tokens_per_file = 8000 * 2  # Threshold for considering a file "large"

    # Setup progress bar
    try:
        from tqdm import tqdm

        files_with_progress = tqdm(
            range(0, len(files)), desc="Analyzing files", unit="file"
        )
    except ImportError:
        # Fallback if tqdm isn't installed
        print("Processing files (install 'tqdm' for progress bar)")
        files_with_progress = range(0, len(files))

    # First, handle large files individually
    large_files = []
    regular_files = []
    
    for i in files_with_progress:
        file_path, relative_path, token_count = files[i]
        
        # Split large files vs regular files
        if token_count > max_tokens_per_file:
            large_files.append((file_path, relative_path, token_count))
        else:
            regular_files.append((file_path, relative_path, token_count))
    
    # Process large files individually
    if large_files:
        print(f"Processing {len(large_files)} large files individually...")
        for file_path, relative_path, _ in large_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    
                summary = generate_summary_for_large_file(
                    file_path, relative_path, content, api_key, model=model
                )
                
                if summary:
                    summaries[relative_path] = summary
                    
            except Exception as e:
                logging.warning(f"Error processing large file {file_path}: {e}")
    
    # Process regular files in batches
    if regular_files:
        print(f"Processing {len(regular_files)} regular files in batches...")
        
        # Process files in batches
        for i in range(0, len(regular_files), batch_size):
            batch = regular_files[i: i + batch_size]
            batch_content = []

            for file_path, relative_path, _ in batch:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    batch_content.append((relative_path, content))
                except Exception as e:
                    logging.warning(f"Error reading {file_path}: {e}")

            # Skip empty batches
            if not batch_content:
                continue

            # Prepare the prompt
            prompt = "I need concise summaries of these files from a codebase. These summaries will be used as context for an LLM to answer questions about the code.\n"
            prompt += "For each file, provide a brief description that:\n"
            prompt += "1. Explains its primary purpose\n"
            prompt += "2. Mentions key functionality or components\n"
            prompt += "3. Captures anything unique or important about its implementation\n"
            prompt += "4. Is optimized to help answer follow-up questions about the code\n\n"
            prompt += "Keep each summary to 1-3 sentences maximum, focused on what would be most helpful for understanding the code.\n\n"

            for relative_path, content in batch_content:
                prompt += f"FILE: {relative_path}\nCONTENT:\n{content}\n\n"

            prompt += "Respond with a JSON object where keys are the file paths and values are the summaries."

            try:
                result = call_openai_api(
                    prompt, api_key, model=model, max_tokens=2000
                )

                if not result:
                    continue

                # Try to parse the JSON response
                try:
                    # Extract JSON if it's wrapped in triple backticks
                    if result.startswith("```json") and result.endswith("```"):
                        result = result[7:-3].strip()
                    elif result.startswith("```") and result.endswith("```"):
                        result = result[3:-3].strip()

                    batch_summaries = json.loads(result)
                    summaries.update(batch_summaries)
                except json.JSONDecodeError:
                    # Fallback: simple parsing if JSON is malformed
                    for relative_path, _ in batch_content:
                        if relative_path in result:
                            parts = result.split(relative_path)
                            if len(parts) > 1:
                                summary_part = parts[1].split("\n\n")[0].strip()
                                summaries[relative_path] = summary_part

            except Exception as e:
                logging.error(f"Error generating summaries: {e}")

    return summaries


def generate_project_context(
    root_dir: str,
    exclude_dirs: Set[str],
    api_key: str,
    output_file: str = "llmcontext.txt",
    max_files: int = 100,
    respect_gitignore: bool = True,
    model: str = None,
) -> None:
    """
    Generate a comprehensive context file about the project for LLMs.
    """
    # Ask for model preference only once at the beginning if not specified
    if model is None:
        default_model = "gpt-3.5-turbo"
        model = ask_for_model_preference(default_model)
        print(f"Using model {model} for all API calls")
        
    print(f"Analyzing project structure in {root_dir}...")

    # Count files first to show progress
    total_files = 0
    
    # Check for .gitignore file and parse patterns
    gitignore_path = os.path.join(root_dir, ".gitignore")
    gitignore_patterns = []
    if respect_gitignore and os.path.isfile(gitignore_path):
        gitignore_patterns = parse_gitignore(gitignore_path)
        print(
            f"Found .gitignore with {len(gitignore_patterns)} patterns - will respect these patterns"
        )
    
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        # Skip directories ignored by gitignore
        if respect_gitignore and gitignore_patterns:
            dirs[:] = [d for d in dirs if not is_ignored_by_gitignore(
                os.path.join(root, d), root_dir, gitignore_patterns)]
                
        for file in files:
            file_path = os.path.join(root, file)
            
            # Skip files ignored by gitignore
            if respect_gitignore and gitignore_patterns and is_ignored_by_gitignore(
                file_path, root_dir, gitignore_patterns
            ):
                continue
                
            if is_text_file(file_path):
                total_files += 1

    print(
        f"Found {total_files} text files to analyze (will select a subset for processing)"
    )

    # Collect files for analysis with token and size limits
    files = collect_files_for_context(
        root_dir, exclude_dirs, max_files=max_files, respect_gitignore=respect_gitignore
    )

    if not files:
        print("No suitable files found for context generation.")
        return

    print(f"Selected {len(files)} representative files for analysis")
    file_summaries = generate_file_summaries(files, api_key, model=model)

    # Group files by directory
    dir_structure = {}
    for file_path, summary in file_summaries.items():
        dir_name = os.path.dirname(file_path)
        if not dir_name:
            dir_name = "/"

        if dir_name not in dir_structure:
            dir_structure[dir_name] = []

        dir_structure[dir_name].append((os.path.basename(file_path), summary))

    # Generate project overview using OpenAI
    project_files_content = "\n".join(
        [f"{file_path}:\n{summary}\n" for file_path, summary in file_summaries.items()]
    )

    try:
        overview_prompt = f"Based on these file summaries from a project, provide a concise overview of what this project appears to be.\n"
        overview_prompt += "This overview will be used as context for an LLM to answer questions about the codebase.\n\n"
        overview_prompt += "Your overview should:\n"
        overview_prompt += "1. Clearly state the project's main purpose and functionality\n"
        overview_prompt += "2. Identify key technologies, frameworks, and languages used\n"
        overview_prompt += "3. Outline the general architecture or main components\n"
        overview_prompt += "4. Be optimized for an LLM to reference when answering follow-up questions about the code\n\n"
        overview_prompt += "Keep it under 5 sentences, focused on the most essential information a developer would need.\n\n"
        overview_prompt += f"FILE SUMMARIES:\n{project_files_content}"

        project_overview = call_openai_api(
            overview_prompt, api_key, model=model, max_tokens=250
        )

        if not project_overview:
            project_overview = "A software project with multiple components."
    except Exception as e:
        logging.error(f"Error generating project overview: {e}")
        project_overview = "A software project with multiple components."

    # Write the context file
    project_name = os.path.basename(os.path.abspath(root_dir))

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"# {project_name}\n\n")
        f.write(f"> {project_overview}\n\n")

        # Write file summaries by directory
        for dir_name, files in sorted(dir_structure.items()):
            if dir_name == "/":
                f.write("## Root Directory\n\n")
            else:
                f.write(f"## {dir_name}/\n\n")

            for filename, summary in sorted(files):
                full_path = (
                    os.path.join(dir_name, filename) if dir_name != "/" else filename
                )
                f.write(f"- **{filename}**: {summary}\n")

            f.write("\n")

    print(f"Project context for LLM has been saved to: {output_file}")


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Generate a directory tree structure and LLM context"
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Root directory to start from (default: current directory)",
    )
    parser.add_argument(
        "--exclude",
        nargs="+",
        default=[
            "node_modules",
            "__pycache__",
            ".git",
            "venv",
            ".env",
            "env",
            "dist",
            "build",
            ".DS_Store",
        ],
        help="Directories to exclude (default: node_modules, __pycache__, .git, venv, etc.)",
    )
    parser.add_argument(
        "--output",
        default="directory_tree.txt",
        help="Output file name (default: directory_tree.txt)",
    )
    parser.add_argument(
        "--llm-context",
        action="store_true",
        help="Generate additional context file for LLMs using OpenAI API",
    )
    parser.add_argument(
        "--context-output",
        default="llmcontext.txt",
        help="Output file for LLM context (default: llmcontext.txt)",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=100,
        help="Maximum number of files to include in context (default: 100)",
    )
    parser.add_argument(
        "--openai-key",
        help="OpenAI API key (if not provided and --llm-context is used, will prompt for it)",
    )
    parser.add_argument(
        "--ignore-gitignore",
        action="store_true",
        help="Ignore .gitignore patterns when generating context (not recommended)",
    )
    parser.add_argument(
        "--model",
        help="OpenAI model to use (if not provided, will prompt once for preference)",
    )
    args = parser.parse_args()

    # Convert exclude_dirs to a set for O(1) lookups
    exclude_dirs = set(args.exclude)

    # Determine absolute path for root directory
    root_dir = os.path.abspath(args.root)

    # Get the directory name
    dir_name = os.path.basename(root_dir)
    if not dir_name:  # Handle case of root directory
        dir_name = root_dir
    
    # Check for .gitignore file and parse patterns for directory tree
    gitignore_patterns = None
    if not args.ignore_gitignore:
        gitignore_path = os.path.join(root_dir, ".gitignore")
        if os.path.isfile(gitignore_path):
            gitignore_patterns = parse_gitignore(gitignore_path)
            print(f"Found .gitignore with {len(gitignore_patterns)} patterns - will respect these patterns")

    # Write the tree to the specified file
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(f"Directory Tree for: {root_dir}\n")
        f.write(f"Excluding: {', '.join(sorted(exclude_dirs))}\n")
        f.write("-" * 50 + "\n")
        f.write(f"{dir_name}/\n")
        write_directory_tree(f, root_dir, exclude_dirs, gitignore_patterns=gitignore_patterns, project_root=root_dir)

    print(f"Directory tree has been saved to: {args.output}")

    # If LLM context generation is requested
    if args.llm_context:
        api_key = args.openai_key

        # If no API key provided, prompt for it
        if not api_key:
            try:
                import getpass

                api_key = getpass.getpass("Enter your OpenAI API key: ")
            except ImportError:
                api_key = input("Enter your OpenAI API key: ")

        if not api_key:
            print("Error: OpenAI API key is required for context generation.")
            return

        # Check if curl is available
        try:
            subprocess.run(["curl", "--version"], capture_output=True, check=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            print(
                "Error: curl command is required for context generation but was not found."
            )
            return

        generate_project_context(
            root_dir,
            exclude_dirs,
            api_key,
            args.context_output,
            args.max_files,
            not args.ignore_gitignore,  # Respect gitignore unless --ignore-gitignore is specified
            args.model,
        )


if __name__ == "__main__":
    main()