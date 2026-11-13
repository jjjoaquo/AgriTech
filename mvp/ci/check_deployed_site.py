"""Check public production pages over verified HTTPS after a deployment."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

OUT = Path(__file__).resolve().parents[1] / "test-results" / "sitio-publicado.json"
PATHS = {
    "/": "AgriTech",
    "/general": "AgriTech",
    "/esparrago": "AgriTech",
    "/cultivo-3d": "AgriTech",
    "/planes": "AgriTech",
    "/login": "AgriTech",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    if not base.startswith("https://"):
        raise SystemExit("La verificación exige HTTPS")
    results = []
    for path, marker in PATHS.items():
        started = time.monotonic()
        try:
            with urlopen(base + path, timeout=15) as response:
                body = response.read(2_000_000).decode("utf-8", errors="replace")
                status = response.status
                final_url = response.url
            ok = status == 200 and marker in body and final_url.startswith("https://")
            error = None if ok else f"HTTP {status}, marca o HTTPS ausente"
        except (HTTPError, URLError, TimeoutError) as exc:
            ok, error, status, final_url = False, str(exc), None, None
        results.append({
            "path": path,
            "ok": ok,
            "status": status,
            "final_url": final_url,
            "seconds": round(time.monotonic() - started, 3),
            "error": error,
        })
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(
        json.dumps({"checked_at_utc": datetime.now(timezone.utc).isoformat(), "base_url": base, "results": results},
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for result in results:
        print(f"{'OK' if result['ok'] else 'FAIL'} {result['path']} {result['status']} {result['seconds']}s")
    if not all(result["ok"] for result in results):
        raise SystemExit("El sitio no superó la verificación pública")


if __name__ == "__main__":
    main()
