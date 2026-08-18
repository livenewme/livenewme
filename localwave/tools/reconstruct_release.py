#!/usr/bin/env python3
import base64
import hashlib
import json
import re
import sys
from pathlib import Path

MAX_APK_BYTES = 100 * 1024 * 1024
VERSION_RE = re.compile(r"^[0-9]+(?:\.[0-9]+){1,3}(?:[-+][0-9A-Za-z.-]+)?$")
SHA_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def fail(message: str):
    raise SystemExit(f"LocalWave release validation failed: {message}")


def main():
    if len(sys.argv) != 4:
        fail("usage: reconstruct_release.py <staging-dir> <output-apk> <output-meta-json>")

    staging = Path(sys.argv[1])
    out_apk = Path(sys.argv[2])
    out_meta = Path(sys.argv[3])
    ready = staging / "READY.json"

    if not ready.is_file():
        fail("READY.json is missing")

    try:
        meta = json.loads(ready.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"READY.json is invalid JSON: {exc}")

    required = ["versionCode", "versionName", "fileName", "sha256", "releaseNotes", "parts"]
    missing = [k for k in required if k not in meta]
    if missing:
        fail("missing fields: " + ", ".join(missing))

    if not isinstance(meta["versionCode"], int) or meta["versionCode"] <= 0:
        fail("versionCode must be a positive integer")

    version_name = str(meta["versionName"])
    if not VERSION_RE.fullmatch(version_name):
        fail("versionName has an unexpected format")

    expected_name = f"LocalWave-v{version_name}.apk"
    if meta["fileName"] != expected_name:
        fail(f"fileName must be exactly {expected_name}")

    sha256 = str(meta["sha256"]).lower()
    if not SHA_RE.fullmatch(sha256):
        fail("sha256 must be exactly 64 hexadecimal characters")

    notes = meta["releaseNotes"]
    if not isinstance(notes, str) or len(notes) > 20000:
        fail("releaseNotes must be a string no longer than 20,000 characters")

    parts = meta["parts"]
    if not isinstance(parts, int) or parts < 1 or parts > 512:
        fail("parts must be an integer from 1 through 512")

    part_dir = staging / "parts"
    expected_parts = [part_dir / f"part-{i:04d}.b64" for i in range(parts)]
    for p in expected_parts:
        if not p.is_file():
            fail(f"missing staging part {p.name}")

    actual_part_names = sorted(p.name for p in part_dir.glob("part-*.b64"))
    expected_part_names = [p.name for p in expected_parts]
    if actual_part_names != expected_part_names:
        fail("staging contains unexpected or incorrectly numbered parts")

    encoded_chunks = []
    encoded_total = 0
    max_b64 = ((MAX_APK_BYTES + 2) // 3) * 4 + 4096
    for p in expected_parts:
        text = "".join(p.read_text(encoding="ascii").split())
        encoded_total += len(text)
        if encoded_total > max_b64:
            fail("encoded APK exceeds maximum permitted size")
        encoded_chunks.append(text)

    try:
        apk = base64.b64decode("".join(encoded_chunks), validate=True)
    except Exception as exc:
        fail(f"Base64 payload is invalid: {exc}")

    if not apk or len(apk) > MAX_APK_BYTES:
        fail("decoded APK has an invalid size")

    if not apk.startswith(b"PK\x03\x04"):
        fail("decoded payload is not an APK/ZIP file")

    actual_sha = hashlib.sha256(apk).hexdigest()
    if actual_sha != sha256:
        fail(f"SHA-256 mismatch: expected {sha256}, got {actual_sha}")

    out_apk.parent.mkdir(parents=True, exist_ok=True)
    out_apk.write_bytes(apk)

    clean_meta = {
        "versionCode": meta["versionCode"],
        "versionName": version_name,
        "fileName": expected_name,
        "sha256": sha256,
        "releaseNotes": notes,
        "parts": parts,
        "dryRun": bool(meta.get("dryRun", False)),
        "sizeBytes": len(apk),
    }
    out_meta.write_text(json.dumps(clean_meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(clean_meta, indent=2))


if __name__ == "__main__":
    main()
