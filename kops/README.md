# kops Cluster Configuration

## Layout

| File | Purpose |
|---|---|
| `cluster.yaml` | Cluster spec — networking, etcd, IAM policy for autoscaler |
| `instancegroups/masters.yaml` | 2x on-demand master IGs (HA control plane) |
| `instancegroups/ig-app-ondemand.yaml` | Mixed-instance-type **on-demand** worker pool (baseline capacity) |
| `instancegroups/ig-app-spot.yaml` | Mixed-instance-type **spot** worker pool (elastic, scales to 0) |

## How "mixed instance group + lifecycle" is satisfied

kops' `mixedInstancesPolicy` lets one Auto Scaling Group span several
EC2 instance types, with `onDemandBase` / `onDemandAboveBase` controlling
the spot/on-demand split:

- **`ig-app-ondemand`**: `onDemandAboveBase: 100` → every instance is
  on-demand, but the ASG can launch any of `m5.large / m5a.large /
  m5n.large / m4.large` depending on availability/price — this is the
  "mixed instance group" requirement applied to the on-demand lifecycle.
- **`ig-app-spot`**: `onDemandAboveBase: 0`, `spotAllocationStrategy:
  capacity-optimized` → same mixed-type pool, but entirely spot, picking
  whichever type currently has the deepest spot capacity (lowest
  interruption risk).

Together the two IGs give you both **lifecycles** (spot + on-demand)
across **multiple instance groups**, each itself spanning multiple
instance types.

## Cluster Autoscaler wiring

Every node IG carries:

```yaml
cloudLabels:
  k8s.io/cluster-autoscaler/enabled: "true"
  k8s.io/cluster-autoscaler/devops-case.k8s.local: "true"
```

These become ASG tags. The Cluster Autoscaler deployment
(`../k8s/cluster-autoscaler.yaml`) uses
`--node-group-auto-discovery=asg:tag=k8s.io/cluster-autoscaler/enabled,k8s.io/cluster-autoscaler/devops-case.k8s.local`
so it manages **both** ASGs automatically — no per-ASG flags needed.

The `ig-app-spot` group also sets
`k8s.io/cluster-autoscaler/node-template/label/*` and
`.../node-template/taint/*` tags so the autoscaler can correctly
simulate scheduling and scale this group up from **0** nodes.

The IAM policy in `cluster.yaml` (`iam.additionalPolicies.node`) grants
worker nodes the `autoscaling:*` permissions the Cluster Autoscaler
needs, scoped via the `k8s.io/cluster-autoscaler/devops-case.k8s.local`
resource tag condition.

## Usage

```bash
export KOPS_STATE_STORE=s3://my-kops-state-store

# Create the cluster from these specs
kops create -f kops/cluster.yaml
kops create -f kops/instancegroups/masters.yaml
kops create -f kops/instancegroups/ig-app-ondemand.yaml
kops create -f kops/instancegroups/ig-app-spot.yaml

# Generate Terraform/cloud resources (or apply directly)
kops update cluster devops-case.k8s.local --yes

# Validate
kops validate cluster devops-case.k8s.local

# Apply k8s and ansible layers after the cluster is up
kubectl apply -f ../k8s/
cd ../ansible && ansible-playbook -i inventory/hosts.ini playbook.yml
```

## Editing later

```bash
kops edit ig ig-app-spot
kops update cluster --yes
kops rolling-update cluster --yes
```
