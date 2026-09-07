#!/usr/bin/env python3
"""Validate the authentik OIDC GitOps integration end to end."""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> str:
    return subprocess.run(
        args,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def docs(text: str) -> list[dict]:
    return [item for item in yaml.safe_load_all(text) if isinstance(item, dict)]


def find(items: list[dict], kind: str, name: str) -> dict:
    for item in items:
        if item.get("kind") == kind and item.get("metadata", {}).get("name") == name:
            return item
    raise AssertionError(f"missing {kind}/{name}")


def main() -> None:
    application = yaml.safe_load((ROOT / "infra/authentik/application.yaml").read_text())
    chart = application["spec"]["sources"][0]
    assert chart["repoURL"] == "https://charts.goauthentik.io"
    assert chart["chart"] == "authentik"
    assert chart["targetRevision"] == "2026.8.1"

    infra_project = yaml.safe_load(
        (ROOT / "bootstrap/projects/project-infra.yaml").read_text()
    )
    assert "https://charts.goauthentik.io" in infra_project["spec"]["sourceRepos"]
    authentik_destination = {
        "namespace": "authentik",
        "server": "https://kubernetes.default.svc",
    }
    assert authentik_destination in infra_project["spec"]["destinations"]
    apps_project = yaml.safe_load(
        (ROOT / "bootstrap/projects/project-apps.yaml").read_text()
    )
    assert authentik_destination in apps_project["spec"]["destinations"]

    blueprint = (ROOT / "infra/authentik/manifests/platform-blueprint.yaml").read_text()
    for expected in (
        "Default - Static MFA setup flow",
        "platform-admins",
        "not_configured_action: configure",
        "device_classes: [totp, static]",
        "session_duration: days=365",
        "remember_me_offset: seconds=0",
        "remember_device: seconds=0",
        "access_token_validity: days=365",
        "refresh_token_validity: days=365",
        "https://argocd.miruohotspring.net/auth/callback",
        "https://concourse.miruohotspring.net/sky/issuer/callback",
        "AUTHENTIK_ARGOCD_CLIENT_SECRET",
        "AUTHENTIK_CONCOURSE_CLIENT_SECRET",
        "slug: platform-invitation-enrollment",
        "designation: enrollment",
        "authentication: require_unauthenticated",
        "authentik_stages_invitation.invitationstage",
        "continue_flow_without_invitation: false",
        "field_key: email",
        "field_key: password",
        "field_key: password_repeat",
        "user_creation_mode: always_create",
        "user_type: internal",
    ):
        assert expected in blueprint, f"blueprint missing {expected}"
    assert blueprint.count("access_token_validity: days=365") == 2
    assert blueprint.count("refresh_token_validity: days=365") == 2
    assert "create_users_group:" not in blueprint

    invitation_stage = blueprint.index("authentik_stages_invitation.invitationstage")
    credentials_stage = blueprint.index("name: platform-invitation-prompt-credentials")
    details_stage = blueprint.index("name: platform-invitation-prompt-details")
    user_write_stage = blueprint.index("authentik_stages_user_write.userwritestage")
    assert invitation_stage < credentials_stage < details_stage < user_write_stage

    runbook = (ROOT / "docs/runbook-authentik.md").read_text()
    for expected in (
        "Directory > Invitations",
        "platform-invitation-enrollment",
        "Single use",
        "24 hours",
        "Copy Link",
        "platform-admins",
    ):
        assert expected in runbook, f"runbook missing invitation guidance: {expected}"

    authentik_render = docs(
        run(
            "helm",
            "template",
            "authentik",
            "authentik",
            "--repo",
            "https://charts.goauthentik.io",
            "--version",
            "2026.8.1",
            "--namespace",
            "authentik",
            "-f",
            str(ROOT / "infra/authentik/values.yaml"),
        )
    )
    ingress = find(authentik_render, "Ingress", "authentik-server")
    assert ingress["spec"]["ingressClassName"] == "nginx"
    assert ingress["spec"]["rules"][0]["host"] == "auth.miruohotspring.net"
    server = find(authentik_render, "Deployment", "authentik-server")
    assert (
        "sha256:9d605ed569ff9f39146be39da93714b2acf19072acc4ab0f0e2f2d81be88cdce"
        in server["spec"]["template"]["spec"]["containers"][0]["image"]
    )
    server_env = {
        item["name"]: item.get("value")
        for item in server["spec"]["template"]["spec"]["containers"][0]["env"]
    }
    assert server_env["AUTHENTIK_POSTGRESQL__HOST"] == "authentik-postgresql"
    assert server_env["AUTHENTIK_POSTGRESQL__PORT"] == "5432"
    assert server_env["AUTHENTIK_POSTGRESQL__NAME"] == "authentik"
    assert server_env["AUTHENTIK_POSTGRESQL__USER"] == "authentik"
    assert server["spec"]["template"]["spec"]["containers"][0]["envFrom"] == [
        {"secretRef": {"name": "authentik-env"}}
    ]
    postgres = find(authentik_render, "StatefulSet", "authentik-postgresql")
    assert (
        "sha256:051f7b7b3abdd564d5d1bd1e8c4b9c1b6e77087d1dd22020ede611c096a272e0"
        in postgres["spec"]["template"]["spec"]["containers"][0]["image"]
    )
    assert postgres["spec"]["volumeClaimTemplates"][0]["spec"]["storageClassName"] == "local-path"

    manifest_render = docs(run("kubectl", "kustomize", "infra/authentik/manifests"))
    find(manifest_render, "ConfigMap", "authentik-blueprints")
    find(manifest_render, "PersistentVolumeClaim", "authentik-postgresql-backups")
    backup = find(manifest_render, "CronJob", "authentik-postgresql-backup")
    backup_script = backup["spec"]["jobTemplate"]["spec"]["template"]["spec"][
        "containers"
    ][0]["args"][0]
    assert "pg_dump --format=custom" in backup_script
    assert 'pg_restore --list "$dump"' in backup_script

    argocd_render = docs(run("kubectl", "kustomize", "apps/argocd"))
    argocd_cm = find(argocd_render, "ConfigMap", "argocd-cm")
    oidc = argocd_cm["data"]["oidc.config"]
    assert "https://auth.miruohotspring.net/application/o/argocd/" in oidc
    assert "clientSecret: $argocd-authentik-oidc:clientSecret" in oidc
    assert 'requestedScopes: ["openid", "profile", "email", "groups"]' in oidc
    assert argocd_cm["data"]["admin.enabled"] == "true"
    params = find(argocd_render, "ConfigMap", "argocd-cmd-params-cm")
    assert params["data"]["users.session.duration"] == "8760h"
    rbac = find(argocd_render, "ConfigMap", "argocd-rbac-cm")
    assert "g, platform-admins, role:admin" in rbac["data"]["policy.csv"]

    concourse_render = docs(
        run(
            "helm",
            "template",
            "concourse",
            "concourse",
            "--repo",
            "https://concourse-charts.storage.googleapis.com/",
            "--version",
            "20.0.1",
            "--namespace",
            "concourse",
            "-f",
            str(ROOT / "infra/concourse/values.yaml"),
        )
    )
    web = find(concourse_render, "Deployment", "concourse-web")
    env = {item["name"]: item for item in web["spec"]["template"]["spec"]["containers"][0]["env"]}
    assert env["CONCOURSE_OIDC_ISSUER"]["value"] == "https://auth.miruohotspring.net/application/o/concourse/"
    assert env["CONCOURSE_OIDC_SCOPE"]["value"] == "profile,email,groups"
    assert env["CONCOURSE_OIDC_GROUPS_KEY"]["value"] == "groups"
    assert env["CONCOURSE_MAIN_TEAM_OIDC_GROUP"]["value"] == "platform-admins"
    assert env["CONCOURSE_AUTH_DURATION"]["value"] == "8760h"
    assert "CONCOURSE_ADD_LOCAL_USER" in env
    assert env["CONCOURSE_OIDC_CLIENT_SECRET"]["valueFrom"]["secretKeyRef"]["key"] == "oidc-client-secret"

    run("kubectl", "kustomize", "infra/concourse")

    sealed = {
        path.name: yaml.safe_load(path.read_text())
        for path in (ROOT / "infra/secrets").glob("*authentik*-sealed.yaml")
    }
    assert "authentik-env-sealed.yaml" in sealed
    assert "authentik-postgresql-sealed.yaml" in sealed
    assert "argocd-authentik-oidc-sealed.yaml" in sealed
    env_keys = sealed["authentik-env-sealed.yaml"]["spec"]["encryptedData"]
    assert {
        "AUTHENTIK_SECRET_KEY",
        "AUTHENTIK_POSTGRESQL__PASSWORD",
        "AUTHENTIK_ARGOCD_CLIENT_SECRET",
        "AUTHENTIK_CONCOURSE_CLIENT_SECRET",
    } <= set(env_keys)

    concourse_secret = yaml.safe_load((ROOT / "infra/secrets/concourse-web-sealed.yaml").read_text())
    assert {"oidc-client-id", "oidc-client-secret"} <= set(concourse_secret["spec"]["encryptedData"])

    for filename, secret_name in (
        ("web-app-template-github-ssh-app-sealed.yaml", "web-app-template-github-ssh-app"),
        (
            "web-app-template-github-ssh-gitops-sealed.yaml",
            "web-app-template-github-ssh-gitops",
        ),
    ):
        ssh_secret = yaml.safe_load((ROOT / "infra/secrets" / filename).read_text())
        assert ssh_secret["metadata"]["name"] == secret_name
        assert ssh_secret["metadata"]["namespace"] == "concourse-main"
        assert "private_key" in ssh_secret["spec"]["encryptedData"]

    print("authentik OIDC GitOps validation passed")


if __name__ == "__main__":
    main()
