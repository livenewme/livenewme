#!/usr/bin/env python3
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def fail(message: str):
    raise SystemExit(f"LocalWave publish failed: {message}")


def main():
    if len(sys.argv) != 4:
        fail("usage: finalize_release.py <meta-json> <verified-apk> <repo-root>")

    meta_path = Path(sys.argv[1])
    apk_path = Path(sys.argv[2])
    repo = Path(sys.argv[3])
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    if meta.get("dryRun"):
        status = {
            "status": "ok",
            "mode": "dry-run",
            "versionCode": meta["versionCode"],
            "versionName": meta["versionName"],
            "sha256": meta["sha256"],
            "sizeBytes": meta["sizeBytes"],
            "checkedAtUtc": datetime.now(timezone.utc).isoformat(),
        }
        out = repo / "localwave" / "pipeline-status.json"
        out.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
        print(f"Dry-run validation complete: {out}")
        return

    latest_path = repo / "localwave" / "latest.json"
    if latest_path.exists():
        current = json.loads(latest_path.read_text(encoding="utf-8"))
        current_code = int(current.get("versionCode", 0))
        if meta["versionCode"] <= current_code:
            fail(f"versionCode {meta['versionCode']} is not newer than current {current_code}")

    release_dir = repo / "localwave" / "releases" / f"v{meta['versionName']}"
    release_dir.mkdir(parents=True, exist_ok=True)
    destination = release_dir / meta["fileName"]
    if destination.exists():
        fail(f"release file already exists: {destination}")
    shutil.copyfile(apk_path, destination)

    raw_url = (
        "https://raw.githubusercontent.com/livenewme/livenewme/main/"
        f"localwave/releases/v{meta['versionName']}/{meta['fileName']}"
    )
    latest = {
        "versionCode": meta["versionCode"],
        "versionName": meta["versionName"],
        "apkUrl": raw_url,
        "sha256": meta["sha256"],
        "releaseNotes": meta["releaseNotes"],
    }
    latest_path.write_text(json.dumps(latest, indent=2) + "\n", encoding="utf-8")

    record = {
        **latest,
        "sizeBytes": meta["sizeBytes"],
        "publishedAtUtc": datetime.now(timezone.utc).isoformat(),
    }
    (release_dir / "release.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared release {meta['versionName']} at {destination}")


if __name__ == "__main__":
    main()
