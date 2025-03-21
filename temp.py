import argparse
import os
import subprocess
import time
from pathlib import Path
import json
import tempfile


with open("text_extentions.json", "r") as f:
    TEXT_EXT = set(json.loads(f.read()))


def get_args():
    parser = argparse.ArgumentParser(description="Generate a directory tree and context for LLM")
    parser.add_argument(
        "--root",
        default=".",
        help="Root directory to start from (default current directory)",
    )
    parser.add_argument(
        "--llm-context",
        action="store_true",
        help="Create short summary of each file suitable for LLM context",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=100,
        help="Maximum number of files allowed to generate summary for",
    )
    parser.add_argument("--ignore-gitignore", action="store_true", help="Ignore .gitignore patterns")
    parser.add_argument(
        "--batch-delay",
        type=float,
        default=5.0,
        help="Delay between each LLM API call for the file summary generations.",
    )
    return parser.parse_args()


def get_dir_name(root_dir):
    dir_name = os.path.basename(root_dir)
    if not dir_name:
        dir_name = root_dir
    return dir_name


def is_gitignored(root_dir, path):
    root_path = Path(root_dir).resolve()
    target_path = Path(path).resolve()
    try:
        rel_path = target_path.relative_to(root_path)
    except ValueError:
        return False
    try:
        result = subprocess.run(
            ["git", "-C", str(root_path), "rev-parse", "--is-inside-work-tree"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            return False

        result = subprocess.run(
            ["git", "-C", str(root_path), "check-ignore", "--quiet", str(rel_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return result.returncode == 0
    except FileNotFoundError:
        raise RuntimeError("Git is not installed.") from None


def ask_for_model_preference(default_model):
    res = input(f"Would you like to use the default model ({default_model}) for all API calls? [Y/n]: ").strip().lower()
    if res == "" or res.lower().startswith("y"):
        print(f"Using default model: {default_model}")
        return default_model

    custom_model = input("Please enter the OpenAI model you would like to use: ").strip()
    if custom_model:
        print(f"Using model: {custom_model} for all API calls")
        return custom_model
    else:
        print(f"No model specified, using default: {default_model}")
        return default_model


def get_all_valid_files(root_dir, respect_gitignore=True):
    collected_files = []
    for root, dirs, files in os.walk(root_dir):
        if ".git" in dirs:
            dirs.remove(".git")

        if respect_gitignore:
            ignored_dirs = []
            for d in dirs:
                dir_path = os.path.join(root, d)
                if is_gitignored(root_dir, dir_path):
                    ignored_dirs.append(d)

            dirs[:] = [d for d in dirs if d not in ignored_dirs]

        for file in sorted(files):
            file_path = os.path.join(root, file)
            if respect_gitignore and is_gitignored(root_dir, file_path):
                continue
            collected_files.append(file_path)

    return collected_files


def is_text_file(file_path: str) -> bool:
    if not os.path.isfile(file_path):
        return False
    try:
        if os.path.getsize(file_path) > 50 * 1024 * 1024:  # 50MB
            return False
    except OSError:
        return False

    text_extensions = TEXT_EXT
    ext = os.path.splitext(file_path)[1].lower()
    if ext in text_extensions:
        return True
    try:
        with open(file_path, "rb") as f:
            if b"\x00" in f.read(1024):
                return False
    except (IOError, OSError):
        return False

    for encoding in ["utf-8", "latin-1", "cp1252"]:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                sample = f.read(1024)
                if sample and sum(c.isprintable() or c in "\n\r\t" for c in sample) / len(sample) > 0.8:
                    return True
        except UnicodeDecodeError:
            continue
        except Exception:
            return False
    return False


def call_openai_api(content, file_path, api_key, project_name, model="gpt-3.5-turbo"):
    prompt = f"""Analyze this file from the '{project_name}' project. These summaries will be used as context for an LLM to understand the codebase.

File path: {file_path}

For your summary:
1. Explain the primary purpose of this file
2. Mention key functionality or components it implements
3. Note any important dependencies or relationships to other files (if apparent)
4. Focus on what would be most helpful for understanding the code's role in the project

Content:
{content}

Provide a concise, informative summary in 1-3 sentences."""

    data = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant that provides concise, technically accurate code summaries for LLM context.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 250,
    }
    fd, temp_path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)

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
    try:
        result = subprocess.run(curl_cmd, capture_output=True, text=True, check=True)
        response = json.loads(result.stdout)
        summary = response["choices"][0]["message"]["content"].strip()
        return summary
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return None
    finally:
        os.unlink(temp_path)


def write_directory_tree(file, root_dir, exclude_dirs={".git"}, prefix="", respect_gitignore=True):
    items = []
    try:
        for item in sorted(os.listdir(root_dir)):
            if item in exclude_dirs:
                continue
            path = os.path.join(root_dir, item)
            if respect_gitignore and is_gitignored(root_dir, path):
                continue
            is_dir = os.path.isdir(path)
            items.append((item, path, is_dir))
    except (PermissionError, FileNotFoundError):
        file.write(f"{prefix}[Access Error]\n")
        return
    for i, (item, path, is_dir) in enumerate(items):
        is_last = i == len(items) - 1
        connector = "└── " if is_last else "├── "
        file.write(f"{prefix}{connector}{item}" + ("/" if is_dir else "") + "\n")
        if is_dir:
            next_prefix = prefix + ("    " if is_last else "│   ")
            write_directory_tree(file, path, exclude_dirs, next_prefix, respect_gitignore)


def create_directory_viz(root_dir, dir_name, respect_gitignore=True):
    tree_file = "directory_tree.txt"
    with open(tree_file, "w", encoding="utf-8") as f:
        f.write(f"{dir_name}/\n")
        write_directory_tree(f, root_dir, respect_gitignore=respect_gitignore)
    print(f"Directory tree saved to: {tree_file}")


def generate_file_summaries(files, root_dir, api_key, project_name, model="gpt-3.5-turbo", batch_delay=2.0):
    summaries = {}
    for file_path in files:
        try:
            # Get path relative to the root directory
            rel_path = os.path.relpath(file_path, root_dir)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            summary = call_openai_api(content, rel_path, api_key, project_name, model)
            if summary:
                summaries[rel_path] = summary
            time.sleep(batch_delay)
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
    return summaries


def get_api_key():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        try:
            import getpass

            api_key = getpass.getpass("Enter your OpenAI API key: ")
        except ImportError:
            api_key = input("Enter your OpenAI API key: ")
    return api_key


def get_dir_structure(summaries):
    dir_structure = {}
    for rel_path, summary in summaries.items():
        dir_name = os.path.dirname(rel_path)
        if not dir_name:
            dir_name = "/"
        if dir_name not in dir_structure:
            dir_structure[dir_name] = []
        dir_structure[dir_name].append((os.path.basename(rel_path), summary))
    return dir_structure


def create_context_file(project_name, dir_structure):
    context_file = "llmcontext.txt"
    with open(context_file, "w", encoding="utf-8") as f:
        f.write(f"# {project_name}\n\n")
        for dir_name, files in sorted(dir_structure.items()):
            if dir_name == "/":
                f.write("## Root Directory\n\n")
            else:
                f.write(f"## {dir_name}/\n\n")

            for filename, summary in sorted(files):
                f.write(f"- **{filename}**: {summary}\n")

            f.write("\n")
    print(f"LLM context has been saved to: {context_file}")


def generate_llmcontext(args, project_name, root_dir):
    if not args.llm_context:
        return

    text_files = get_all_valid_files(root_dir, respect_gitignore=not args.ignore_gitignore)
    text_files = [ele for ele in text_files if is_text_file(ele)]

    if len(text_files) > args.max_files:
        print(f"Limiting to {args.max_files} files for summaries")
        text_files = text_files[: args.max_files]
    api_key = get_api_key()
    model = ask_for_model_preference("gpt-3.5-turbo-16k")
    summaries = generate_file_summaries(text_files, root_dir, api_key, project_name, model, args.batch_delay)
    dir_structure = get_dir_structure(summaries)
    create_context_file(project_name, dir_structure)


def main():
    args = get_args()
    root_dir = os.path.abspath(args.root)
    dir_name = get_dir_name(root_dir)
    create_directory_viz(root_dir, dir_name)
    generate_llmcontext(args, dir_name, root_dir)


main()