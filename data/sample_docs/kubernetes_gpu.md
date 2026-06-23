# Running GPU Workloads on Kubernetes

Kubernetes can schedule GPU workloads once the cluster exposes GPUs as a
schedulable resource.

## The NVIDIA device plugin

The NVIDIA device plugin runs as a DaemonSet and advertises `nvidia.com/gpu` as a
resource on each node. Pods request GPUs through resource limits:

```yaml
resources:
  limits:
    nvidia.com/gpu: 1
```

A pod is only scheduled onto a node with a free GPU matching its request.

## Readiness and liveness probes

An inference Deployment should expose a `/health` endpoint and wire it to a
readiness probe so traffic is only routed once the model is loaded, and to a
liveness probe so a wedged process is restarted. Model loading can take tens of
seconds, so set `initialDelaySeconds` generously.

## ConfigMaps and Secrets

Non-sensitive configuration (model name, index type, top-k) belongs in a
ConfigMap mounted as environment variables. API keys belong in a Secret, never in
the image or a ConfigMap.

## Autoscaling

The Horizontal Pod Autoscaler can scale inference replicas on CPU or custom
metrics such as request latency or queue depth, but GPU availability caps how far
replicas can scale on a fixed cluster.
