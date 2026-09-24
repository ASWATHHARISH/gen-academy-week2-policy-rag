"""Build an allowlisted cloud-publication copy without changing the local app."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import get_settings
from scripts.package_submission import selected_files


def main():
    target = ROOT / 'artifacts' / 'publication'
    if target.exists():
        raise FileExistsError('Publication copy already exists; do not overwrite it.')
    files = list(selected_files())
    secret = get_settings().google_api_key.get_secret_value().encode()
    payloads = {}
    for source in files:
        relative = source.relative_to(ROOT).as_posix()
        data = source.read_bytes()
        if secret and secret in data:
            raise RuntimeError('Secret found; publication copy stopped.')
        if relative == '.streamlit/config.toml':
            text = data.decode('utf-8')
            expected = 'address = "127.0.0.1"'
            if text.count(expected) != 1:
                raise RuntimeError('Local bind setting changed; review publication config.')
            data = text.replace(expected, '# Cloud copy: use the hosting platform listener default.').encode('utf-8')
        payloads[relative] = data
    for relative, data in payloads.items():
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    manifest = {'files': [{'path': name, 'sha256': hashlib.sha256(data).hexdigest()}
                         for name, data in sorted(payloads.items())],
                'transformation': 'Only publication .streamlit/config.toml omits local loopback binding.',
                'excluded': ['.env', 'API ledger', '.venv', 'model cache', 'Chroma', 'media artifacts']}
    (ROOT / 'artifacts' / 'publication_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(f'Created sanitized publication copy with {len(payloads)} files. Local configuration unchanged.')


if __name__ == '__main__':
    main()
