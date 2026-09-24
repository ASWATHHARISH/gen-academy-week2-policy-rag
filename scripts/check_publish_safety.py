"""Fail closed before publishing staged project files; never print credentials."""
from pathlib import Path
import subprocess
import sys
import argparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import get_settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=ROOT)
    repo = parser.parse_args().repo.resolve()
    secret = get_settings().google_api_key.get_secret_value().encode()
    files = subprocess.check_output(['git', 'diff', '--cached', '--name-only', '-z'], cwd=repo).decode().split('\0')
    files = [name for name in files if name]
    if not files:
        raise RuntimeError('No staged files to check.')
    for name in files:
        parts = Path(name).parts
        if (name == '.env' or any(part in {'.cache', '.venv', 'artifacts', 'chroma'} for part in parts)
                or Path(name).name.startswith(('api_budget', 'secrets.'))):
            raise RuntimeError('A private/runtime path was staged; publication stopped.')
        content = subprocess.check_output(['git', 'show', ':' + name], cwd=repo)
        if secret and secret in content:
            raise RuntimeError('A staged artifact contains a configured credential; publication stopped.')
        if Path(name).suffix in {'.json', '.jsonl', '.html'} and content != (repo / name).read_bytes():
            raise RuntimeError('Frozen bytes changed during staging; publication stopped.')
    required = {'data/processed/chunks256/chunks.jsonl', 'data/processed/chunks256/index_manifest.json',
                'deployment/streamlit_app.py', 'deployment/requirements.txt',
                'evaluation/results/p1_hybrid_256_evaluation.json'}
    tracked = set(subprocess.check_output(['git', 'ls-files', '-z'], cwd=repo).decode().split('\0'))
    if not required.issubset(tracked):
        raise RuntimeError('A required deployment input is missing.')
    print(f'Publication safety passed for {len(files)} staged files: no configured key/private caches; frozen bytes preserved.')


if __name__ == '__main__':
    main()
