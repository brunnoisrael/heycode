"""The VM firewall consumes this file without Windows line endings."""

import subprocess
from pathlib import Path


def test_cloudflare_ip_list_checkout_uses_lf():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["git", "-c", "core.autocrlf=true", "checkout-index", "--temp", "infra/vps/cloudflare-ips.txt"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    checkout = root / result.stdout.split("\t", 1)[0]
    try:
        content = checkout.read_bytes()
        assert b"\r" not in content
        assert b"173.245.48.0/20\n" in content
    finally:
        checkout.unlink(missing_ok=True)
