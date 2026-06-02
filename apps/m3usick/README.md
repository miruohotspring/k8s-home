# m3usick Argo CD app-of-apps

This directory registers the m3usick GitOps repository with the home-cluster Argo CD root app.

- `application.yaml` creates `m3usick-apps`.
- `m3usick-apps` reads `https://github.com/gammaLaboratory/m3usick-gitops.git` at `infra/argocd/`.
- The dedicated GitOps repository owns the environment Applications and Kustomize manifests.
