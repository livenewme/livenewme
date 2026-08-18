#!/usr/bin/env python3
import argparse
import base64
import hashlib
import json
import shutil
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description="Prepare an already-signed LocalWave APK for the GitHub publishing pipeline.")
    ap.add_argument("apk", type=Path)
    ap.add_argument("version_code", type=int)
    ap.add_argument("version_name")
    ap.add_argument("--notes", default="")
    ap.add_argument("--notes-file", type=Path)
    ap.add_argument("--output", type=Path, default=Path("localwave/staging"))
    ap.add_argument("--chunk-chars", type=int, default=16000)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.version_code <= 0:
        raise SystemExit("version_code must be positive")
    if args.chunk_chars < 4096 or args.chunk_chars > 250000 or args.chunk_chars % 4:
        raise SystemExit("--chunk-chars must be 4,096..250,000 and divisible by 4")
    if not args.apk.is_file():
        raise SystemExit(f"APK not found: {args.apk}")

    raw = args.apk.read_bytes()
    if not raw.startswith(b"PK\x03\x04"):
        raise SystemExit("input does not look like an APK/ZIP")
    if len(raw) > 100 * 1024 * 1024:
        raise SystemExit("APK is larger than the pipeline's 100 MiB limit")

    notes = args.notes_file.read_text(encoding="utf-8") if args.notes_file else args.notes
    if len(notes) > 20000:
        raise SystemExit("release notes exceed 20,000 characters")

    out = args.output
    if out.exists():
        shutil.rmtree(out)
    parts_dir = out / "parts"
    parts_dir.mkdir(parents=True)

    encoded = base64.b64encode(raw).decode("ascii")
    chunks = [encoded[i:i + args.chunk_chars] for i in range(0, len(encoded), args.chunk_chars)]
    for i, chunk in enumerate(chunks):
        (parts_dir / f"part-{i:04d}.b64").write_text(chunk + "\n", encoding="ascii")

    version_name = str(args.version_name)
    file_name = f"LocalWave-v{version_name}.apk"
    ready = {
        "versionCode": args.version_code,
        "versionName": version_name,
        "fileName": file_name,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "releaseNotes": notes,
        "parts": len(chunks),
        "dryRun": bool(args.dry_run),
    }
    (out / "READY.json").write_text(json.dumps(ready, indent=2) + "\n", encoding="utf-8")

    print(f"Prepared {file_name}")
    print(f"  bytes:  {len(raw)}")
    print(f"  sha256: {ready['sha256']}")
    print(f"  parts:  {len(chunks)} x <= {args.chunk_chars} Base64 chars")
    print("Upload every parts/part-*.b64 first. Upload READY.json last; that file triggers publication.")


if __name__ == "__main__":
    main()
