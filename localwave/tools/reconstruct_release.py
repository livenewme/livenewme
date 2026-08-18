#!/usr/bin/env python3
import base64
import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

MAX_APK_BYTES = 100 * 1024 * 1024
MAX_TAIL_BYTES = 4 * 1024 * 1024
VERSION_RE = re.compile(r"^[0-9]+(?:\.[0-9]+){1,3}(?:[-+][0-9A-Za-z.-]+)?$")
SHA_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def fail(message: str):
    raise SystemExit(f"LocalWave release validation failed: {message}")


def decode_parts(directory: Path, count: int, max_decoded_bytes: int) -> bytes:
    expected = [directory / f"part-{i:04d}.b64" for i in range(count)]
    for p in expected:
        if not p.is_file():
            fail(f"missing staging part {p.name}")

    actual_names = sorted(p.name for p in directory.glob("part-*.b64"))
    expected_names = [p.name for p in expected]
    if actual_names != expected_names:
        fail("staging contains unexpected or incorrectly numbered parts")

    chunks = []
    encoded_total = 0
    max_b64 = ((max_decoded_bytes + 2) // 3) * 4 + 4096
    for p in expected:
        text = "".join(p.read_text(encoding="ascii").split())
        encoded_total += len(text)
        if encoded_total > max_b64:
            fail("encoded payload exceeds maximum permitted size")
        chunks.append(text)

    try:
        data = base64.b64decode("".join(chunks), validate=True)
    except Exception as exc:
        fail(f"Base64 payload is invalid: {exc}")

    if len(data) > max_decoded_bytes:
        fail("decoded payload exceeds maximum permitted size")
    return data


def main():
    if len(sys.argv) not in (4, 5):
        fail("usage: reconstruct_release.py <staging-dir> <output-apk> <output-meta-json> [unsigned-apk]")

    staging = Path(sys.argv[1])
    out_apk = Path(sys.argv[2])
    out_meta = Path(sys.argv[3])
    unsigned_path = Path(sys.argv[4]) if len(sys.argv) == 5 else None
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

    transport = str(meta.get("transportMode", "full-base64"))

    if transport == "full-base64":
        apk = decode_parts(staging / "parts", parts, MAX_APK_BYTES)

    elif transport == "unsigned-artifact-tail":
        if unsigned_path is None or not unsigned_path.is_file():
            fail("unsigned-artifact-tail transport requires an unsigned APK input")

        unsigned_sha = str(meta.get("unsignedApkSha256", "")).lower()
        if not SHA_RE.fullmatch(unsigned_sha):
            fail("unsignedApkSha256 must be exactly 64 hexadecimal characters")

        unsigned = unsigned_path.read_bytes()
        if not unsigned or len(unsigned) > MAX_APK_BYTES:
            fail("unsigned APK has an invalid size")
        if not unsigned.startswith(b"PK\x03\x04"):
            fail("unsigned source is not an APK/ZIP file")
        actual_unsigned_sha = hashlib.sha256(unsigned).hexdigest()
        if actual_unsigned_sha != unsigned_sha:
            fail(f"unsigned APK SHA-256 mismatch: expected {unsigned_sha}, got {actual_unsigned_sha}")

        prefix = meta.get("prefixBytes")
        if not isinstance(prefix, int) or prefix < 0 or prefix > len(unsigned):
            fail("prefixBytes is outside the unsigned APK")

        compression = str(meta.get("tailCompression", "none"))
        tail_dir = staging / ("gzip-tail" if compression == "gzip" else "tail")
        encoded_tail = decode_parts(tail_dir, parts, MAX_TAIL_BYTES)

        if compression == "gzip":
            compressed_sha = str(meta.get("compressedTailSha256", "")).lower()
            if not SHA_RE.fullmatch(compressed_sha):
                fail("compressedTailSha256 must be exactly 64 hexadecimal characters")
            actual_compressed_sha = hashlib.sha256(encoded_tail).hexdigest()
            if actual_compressed_sha != compressed_sha:
                fail(f"compressed tail SHA-256 mismatch: expected {compressed_sha}, got {actual_compressed_sha}")
            try:
                tail = gzip.decompress(encoded_tail)
            except Exception as exc:
                fail(f"gzip signing tail is invalid: {exc}")
        elif compression == "none":
            tail = encoded_tail
        else:
            fail(f"unsupported tailCompression: {compression}")

        if not tail or len(tail) > MAX_TAIL_BYTES:
            fail("signed tail has an invalid size")
        apk = unsigned[:prefix] + tail

    else:
        fail(f"unsupported transportMode: {transport}")

    if not apk or len(apk) > MAX_APK_BYTES:
        fail("reconstructed APK has an invalid size")
    if not apk.startswith(b"PK\x03\x04"):
        fail("reconstructed payload is not an APK/ZIP file")

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
        "transportMode": transport,
        "dryRun": bool(meta.get("dryRun", False)),
        "sizeBytes": len(apk),
    }
    out_meta.write_text(json.dumps(clean_meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(clean_meta, indent=2))


if __name__ == "__main__":
    main()
