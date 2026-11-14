# m3usick Argo CD app-of-apps

This directory registers the private m3usick GitOps repository with the home-cluster Argo CD root app.

- `application.yaml` creates `m3usick-apps`.
- `m3usick-apps` reads `git@github.com:gammaLaboratory/m3usick-gitops.git` at `infra/argocd/`.
- `infra/secrets/argocd-repo-m3usick-gitops-sealed.yaml` provides the repository-scoped read-only deploy key.
- The dedicated GitOps repository owns the environment Applications and Kustomize manifests.
