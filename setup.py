from setuptools import setup, find_packages

setup(
    name="llmdirtree",
    version="0.1.4",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "llmdirtree=dirtree.main:main",
        ],
    },
    author="arun",
    author_email="your.email@example.com",
    description="A simple directory tree generator for llm",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/arun477/dirtree",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    extras_require={
        "progress": ["tqdm"],  # Optional for progress bars
    },
    python_requires=">=3.6",
)