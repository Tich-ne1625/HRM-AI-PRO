# Local Kubernetes artifacts

Read the [Vietnamese setup and recovery guide](../../docs/kubernetes.vi.md).

- `base/`: API/web Deployments, PostgreSQL StatefulSet/PVC, ClusterIP Services, nonsecret ConfigMap and web-only Ingress.
- `overlays/local-http/`: test-mode same-origin access on localhost:13010.
- `overlays/local-https/`: secure-cookie production config on insighthr.test:13443; requires a separately created TLS Secret.
- `versions.json`: pinned tools and observed image identity.

Secrets, cluster kubeconfig and private keys are generated outside Git. The runner creates a separate migration Job under a namespace Lease before application rollout; it is intentionally absent from the regular Kustomize bundle. Both profiles are strictly validated against the local API server before use. Default namespace is the disposable acceptance namespace; pass `--namespace insighthr-local` for practice.

Never publish the same localhost ingress from both namespaces simultaneously. No API/DB NodePort, user volume mount, default-context switch or live Gemini call is needed. See the [contract](../../docs/phase-10-contract.md) and [execution plan](../../docs/superpowers/plans/2026-10-24-phase-10-kubernetes-docs.md) for acceptance boundaries.
