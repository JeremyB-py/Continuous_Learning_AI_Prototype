#!/usr/bin/env python3
"""
setup_repo.py
-------------
Bootstrap script for the CLAIP (Continuous Learning AI Prototype) repository.

Creates folder structure, placeholder files, and starter documentation
consistent with README.md. Safe to rerun; it won't overwrite existing files.
"""

import os
from pathlib import Path

# --- Configuration ---
ROOT = Path(__file__).parent.resolve()

FOLDERS = [
    "src",
    "data/example_datasets",
    "docs",
    "logs",
    "reports",
    "checkpoints",
    "licenses",
]

FILES = {
    "src/__init__.py": "",
    "src/CLAIP.py": '"""Continuous Learner Core Module"""\n\nclass ContinuousLearner:\n    def __init__(self):\n        pass\n',
    "src/ethics.py": '"""Moral Enforcement Module"""\n\nfrom dataclasses import dataclass\n\n@dataclass(frozen=True)\nclass MoralRules:\n    never_harm_living: bool = True\n    reasonable_outweighs_unreasonable: bool = True\n    do_not_purposefully_deceive: bool = True\n',
    "src/checkpoint.py": '"""Checkpoint & Rollback Utility"""\n\ndef create_checkpoint():\n    pass\n\ndef restore_checkpoint():\n    pass\n',
    "src/shadow_eval.py": '"""Shadow Evaluation Framework"""\n\ndef run_shadow_eval():\n    pass\n',
    "docs/LIMITATIONS_AND_SAFEGUARDS.md": "# Limitations and Safeguards\n\n(See project documentation for risk analysis.)\n",
    "docs/EVALUATION_AND_CHECKPOINT_PROTOCOL.md": "# Evaluation and Checkpoint Protocol\n\n(See project documentation for testing procedures.)\n",
    "docs/research_notes.md": "# Research Notes\nA living document for theoretical ideas and experiments.\n",
    "data/example_datasets/README.md": "# Example Datasets\nPlace small example CSVs here for toy testing.\n",
    "logs/journal.log": "",
    "reports/.gitkeep": "",
    "checkpoints/.gitkeep": "",
    "requirements.txt": "pandas\nnumpy\nscikit-learn\nmatplotlib\n# Optional: online learning\nriver\n",
    ".gitignore": "__pycache__/\n*.pyc\n*.pyo\n*.pkl\n*.sqlite\n.env\n*.log\ncheckpoints/\nreports/\nlogs/\ndata/\n",
    "licenses/LICENSE.docs": "Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)\n\nThis license applies to documentation and moral framework content.\nSee https://creativecommons.org/licenses/by-sa/4.0/legalcode\n",
    "LICENSE": "MIT License\n\nCopyright (c) 2025 [Your Name]\n\nPermission is hereby granted, free of charge, to any person obtaining a copy\nof this software and associated documentation files (the \"Software\"), to deal\nin the Software without restriction, including without limitation the rights\nto use, copy, modify, merge, publish, distribute, sublicense, and/or sell\ncopies of the Software, and to permit persons to whom the Software is\nfurnished to do so, subject to the following conditions:\n\n[... full MIT text ...]\n",
}

def ensure_folder(path: Path):
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        print(f"📁 Created folder: {path.relative_to(ROOT)}")

def ensure_file(path: Path, content: str):
    if not path.exists():
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"📝 Created file: {path.relative_to(ROOT)}")
    else:
        print(f"✔️  Exists: {path.relative_to(ROOT)}")

def main():
    print("\n🧱 Setting up CLAIP repository structure...\n")

    for folder in FOLDERS:
        ensure_folder(ROOT / folder)

    for file_path, content in FILES.items():
        ensure_file(ROOT / file_path, content)

    print("\n✅ Repository scaffolding complete.\n")

if __name__ == "__main__":
    main()
