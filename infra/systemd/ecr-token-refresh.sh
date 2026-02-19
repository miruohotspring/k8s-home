#!/bin/bash
# ECR token refresh script for k3s nodes
# Runs as a systemd service (ecr-token-refresh.service)
# Credentials loaded from /etc/ecr-token-refresh/credentials via EnvironmentFile

set -euo pipefail

AWS_REGION="${AWS_REGION:-ap-northeast-1}"
ECR_REGISTRY="${ECR_REGISTRY:-004908959120.dkr.ecr.ap-northeast-1.amazonaws.com}"
KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"

echo "[$(date -Iseconds)] Starting ECR token refresh"

TOKEN=$(aws ecr get-login-password --region "${AWS_REGION}")

for NS in default example-dev; do
  kubectl --kubeconfig="${KUBECONFIG}" create secret docker-registry ecr-secret \
    --docker-server="${ECR_REGISTRY}" \
    --docker-username=AWS \
    --docker-password="${TOKEN}" \
    --namespace="${NS}" \
    --dry-run=client -o yaml | kubectl --kubeconfig="${KUBECONFIG}" apply -f -
  echo "[$(date -Iseconds)] Updated ecr-secret in ${NS}"
done

echo "[$(date -Iseconds)] ECR token refresh completed successfully"
