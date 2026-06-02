# m3usick Argo CD Applications

This directory registers the m3usick web app environments with the home-cluster Argo CD root app.

- `dev/application.yaml` manages `m3usick-dev` from `gammaLaboratory/jarvis-miruo-v2:projects/m3usick/app/overlays/dev`.
- `prod/application.yaml` manages `m3usick-prod` from `gammaLaboratory/jarvis-miruo-v2:projects/m3usick/app/overlays/prod`.

The app manifests live in `jarvis-miruo-v2` because that repository owns project orchestration. The `apps` AppProject must allow the jarvis repo plus both m3usick namespaces.
