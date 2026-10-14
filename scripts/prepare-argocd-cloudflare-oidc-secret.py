#!/usr/bin/env python3
"""Emit an Argo CD Cloudflare Access Secret for immediate sealing.

The process captures Terraform's sensitive client output in memory. Argo CD
administrator identities come from a separate owner-only JSON file; ordinary
application membership remains Web-managed in Cloudflare Access. Standard
output is Kubernetes Secret YAML intended only for a kubeseal pipe.
"""
import argparse
import base64
import json
import pathlib
import re
import subprocess
import sys
from typing import Any
from urllib.parse import quote


EMAIL = re.compile(r"^[^,@\r\n]+@[^,@\r\n]+\.[^,@\r\n]+$")
TEAM = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
CLIENT_ID = re.compile(r"^[A-Za-z0-9._~-]+$")


def terraform_json(terraform_dir: pathlib.Path, *args: str) -> Any:
    completed = subprocess.run(
        ["terraform", f"-chdir={terraform_dir}", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError("Terraform read failed; no sensitive command output was emitted")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Terraform returned invalid JSON") from exc


def load_admin_emails(path: pathlib.Path) -> list[str]:
    try:
        if path.stat().st_mode & 0o077:
            raise RuntimeError("The Argo CD admin email file must use owner-only permissions")
        values = json.loads(path.read_text())
    except OSError as exc:
        raise RuntimeError("The Argo CD admin email file could not be read") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("The Argo CD admin email file is not valid JSON") from exc

    if not isinstance(values, list) or not values:
        raise RuntimeError("The Argo CD admin email file must contain a non-empty JSON array")
    if any(not isinstance(value, str) or not EMAIL.fullmatch(value) for value in values):
        raise RuntimeError("The Argo CD admin email file contains an invalid email value")
    return sorted(set(values), key=str.casefold)


def encode(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--terraform-dir", type=pathlib.Path, required=True)
    parser.add_argument("--team-name", required=True)
    parser.add_argument("--admin-emails-file", type=pathlib.Path, required=True)
    args = parser.parse_args()

    if not TEAM.fullmatch(args.team_name):
        raise RuntimeError("Cloudflare team name is invalid")

    clients = terraform_json(args.terraform_dir, "output", "-json", "saas_clients")
    try:
        argocd_client = clients["argocd"]
        client_id = argocd_client["client_id"]
        client_secret = argocd_client["client_secret"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError("The Argo CD SaaS client output is incomplete") from exc

    if not isinstance(client_id, str) or not CLIENT_ID.fullmatch(client_id):
        raise RuntimeError("The Argo CD client ID is invalid")
    if not isinstance(client_secret, str) or not client_secret or "\r" in client_secret or "\n" in client_secret:
        raise RuntimeError("The Argo CD client secret is invalid")

    emails = load_admin_emails(args.admin_emails_file)
    policy = "".join(f"g, {email}, platform-admins\n" for email in emails)
    patch = json.dumps({"data": {"policy.cloudflare.csv": policy}}, separators=(",", ":"))
    issuer = f"https://{args.team_name}.cloudflareaccess.com/cdn-cgi/access/sso/oidc/{quote(client_id, safe='') }"

    data = {
        "issuer": issuer,
        "clientID": client_id,
        "clientSecret": client_secret,
        "rbac-patch.json": patch,
    }
    encoded = "\n".join(f"  {key}: {encode(value)}" for key, value in data.items())
    sys.stdout.write(
        "apiVersion: v1\n"
        "kind: Secret\n"
        "metadata:\n"
        "  name: argocd-cloudflare-oidc\n"
        "  namespace: argocd\n"
        "  labels:\n"
        "    app.kubernetes.io/part-of: argocd\n"
        "type: Opaque\n"
        "data:\n"
        f"{encoded}\n"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
