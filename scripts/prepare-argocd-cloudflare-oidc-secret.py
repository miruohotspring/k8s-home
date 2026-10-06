#!/usr/bin/env python3
"""Emit an Argo CD Cloudflare Access Secret for immediate sealing.

The process captures Terraform's sensitive client output and state in memory. Its
standard output is Kubernetes Secret YAML intended only for a kubeseal pipe.
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


def resources(module: dict) -> list[dict]:
    found = list(module.get("resources", []))
    for child in module.get("child_modules", []):
        found.extend(resources(child))
    return found


def extract_argocd_emails(state: dict) -> list[str]:
    target = 'cloudflare_zero_trust_access_policy.allow_email_otp_totp["argocd"]'
    match = next(
        (item for item in resources(state["values"]["root_module"]) if item.get("address") == target),
        None,
    )
    if match is None:
        raise RuntimeError("The Argo CD allowlist policy is absent from Terraform state")

    emails: set[str] = set()
    for selector in match["values"].get("include", []):
        for name, value in selector.items():
            if value is None:
                continue
            if name != "email" or not isinstance(value, dict) or set(value) != {"email"}:
                raise RuntimeError("The Argo CD allowlist contains an unsupported identity selector")
            email = value["email"]
            if not isinstance(email, str) or not EMAIL.fullmatch(email):
                raise RuntimeError("The Argo CD allowlist contains an invalid email value")
            emails.add(email)

    if not emails:
        raise RuntimeError("The Argo CD allowlist has no email identities")
    return sorted(emails, key=str.casefold)


def encode(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--terraform-dir", type=pathlib.Path, required=True)
    parser.add_argument("--team-name", required=True)
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

    state = terraform_json(args.terraform_dir, "show", "-json")
    emails = extract_argocd_emails(state)
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
