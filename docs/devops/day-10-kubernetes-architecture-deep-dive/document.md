# Day 10: Document — Kubernetes Architecture Reference

## 1. Kubernetes Architecture Diagram

```
┌─────────────────────────── Control Plane ───────────────────────────┐
│                                                                      │
│  ┌──────────────┐  ┌──────────┐  ┌────────────────┐  ┌──────────┐ │
│  │  API Server  │  │  etcd    │  │ Controller Mgr │  │Scheduler │ │
│  │  Port: 6443  │──│ Port:2379│──│ Port: 10257    │  │Port:10259│ │
│  │              │  │          │  │                 │  │          │ │
│  │ Gateway      │  │ State    │  │ Reconciliation │  │ Pod      │ │
│  │ Auth/Authz   │  │ Store    │  │ Loops          │  │Placement │ │
│  │ Admission    │  │ Raft     │  │ Self-healing   │  │ Scoring  │ │
│  └──────────────┘  └──────────┘  └────────────────┘  └──────────┘ │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
                              │ Network
┌──────────────────────────── Worker Nodes ────────────────────────────┐
│                                                                      │
│  ┌─── Node ────────────────────────────────────────────────────┐    │
│  │  ┌──────────┐  ┌────────────┐  ┌──────────────────────┐   │    │
│  │  │ kubelet  │  │ kube-proxy │  │ Container Runtime    │   │    │
│  │  │ Port:    │  │            │  │ (containerd/CRI-O)   │   │    │
│  │  │ 10250    │  │ iptables/  │  │                      │   │    │
│  │  │          │  │ IPVS/eBPF  │  │ containerd → runc    │   │    │
│  │  └──────────┘  └────────────┘  └──────────────────────┘   │    │
│  │                                                            │    │
│  │  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐                 │    │
│  │  │Pod A │  │Pod B │  │Pod C │  │Pod D │                 │    │
│  │  └──────┘  └──────┘  └──────┘  └──────┘                 │    │
│  └────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. Control Plane Component Reference

| Component | Port | Role | Failure Impact | Recovery |
|-----------|------|------|----------------|----------|
| **API Server** | 6443 | Gateway, auth, validation, etcd access | Cluster unreachable, no management | Restart, HA: LB + multiple instances |
| **etcd** | 2379, 2380 | Cluster state store (Raft consensus) | Cluster "frozen", no state changes | Restore from backup, need quorum |
| **Controller Manager** | 10257 | Runs reconciliation controllers | No self-healing, no scaling | Restart, leader election |
| **Scheduler** | 10259 | Places pods on nodes | New pods stuck Pending | Restart, leader election |
| **Cloud Controller** | 10258 | Cloud provider integration | LB/routes not updated | Restart |

### Component Dependencies

```
kubectl → API Server → etcd (read/write state)
                     → Admission Webhooks (validate/mutate)

Scheduler → API Server (watch unscheduled pods, bind to node)

Controller Manager → API Server (watch objects, create/update/delete)
  ├── Deployment Controller
  ├── ReplicaSet Controller
  ├── Node Controller
  ├── Service Controller
  ├── Job Controller
  ├── Endpoint Controller
  └── Namespace Controller

Kubelet → API Server (watch pods for this node, report status)
       → Container Runtime (CRI: create/start/stop containers)

kube-proxy → API Server (watch Services/Endpoints)
          → iptables/IPVS (configure routing rules)
```

---

## 3. kubectl Essential Commands

### Cluster Management

```bash
# Cluster info
kubectl cluster-info                    # Cluster endpoint
kubectl get nodes -o wide               # Node list with details
kubectl top nodes                       # Node resource usage

# Component health
kubectl get --raw /healthz              # API server health
kubectl get --raw /readyz               # API server readiness
kubectl get componentstatuses           # Component status (deprecated)

# Config
kubectl config view                     # kubeconfig
kubectl config get-contexts             # Available contexts
kubectl config use-context CONTEXT      # Switch context
kubectl config current-context          # Current context
```

### Resource Operations

```bash
# Get resources
kubectl get pods                        # List pods (default namespace)
kubectl get pods -A                     # All namespaces
kubectl get pods -o wide                # Extra columns (node, IP)
kubectl get pods -o yaml                # Full YAML
kubectl get pods -o json                # Full JSON
kubectl get pods -l app=nginx           # Filter by label
kubectl get pods --field-selector spec.nodeName=worker1  # Filter by field
kubectl get pods --sort-by=.metadata.creationTimestamp    # Sort

# Describe (detailed info + events)
kubectl describe pod POD_NAME
kubectl describe node NODE_NAME
kubectl describe deployment DEPLOY_NAME

# Create/Apply
kubectl apply -f manifest.yaml          # Declarative (recommended)
kubectl create -f manifest.yaml         # Imperative create
kubectl run nginx --image=nginx         # Quick pod

# Edit
kubectl edit deployment DEPLOY_NAME     # Open in editor
kubectl patch deployment NAME -p '{"spec":{"replicas":5}}'

# Delete
kubectl delete -f manifest.yaml
kubectl delete pod POD_NAME
kubectl delete pod POD_NAME --grace-period=0 --force  # Force delete
```

### Debugging

```bash
# Logs
kubectl logs POD_NAME                   # Current logs
kubectl logs POD_NAME -c CONTAINER      # Specific container
kubectl logs POD_NAME --previous        # Previous crash logs
kubectl logs POD_NAME -f                # Follow (stream)
kubectl logs POD_NAME --since=5m        # Last 5 minutes
kubectl logs -l app=nginx               # By label

# Execute
kubectl exec POD_NAME -- ls /           # Run command
kubectl exec -it POD_NAME -- sh         # Interactive shell
kubectl exec POD_NAME -c CONTAINER -- CMD  # Specific container

# Port forward
kubectl port-forward pod/POD_NAME 8080:80    # Pod
kubectl port-forward svc/SVC_NAME 8080:80    # Service
kubectl port-forward deploy/DEPLOY 8080:80   # Deployment

# Debug (ephemeral container)
kubectl debug POD_NAME -it --image=busybox   # Attach debug container
kubectl debug node/NODE_NAME -it --image=busybox  # Node debug

# Events
kubectl get events                           # All events
kubectl get events --sort-by='.lastTimestamp' # Sorted
kubectl get events --field-selector type=Warning  # Warnings only
kubectl get events -w                        # Watch

# Resource usage
kubectl top pods                        # Pod CPU/memory
kubectl top pods --sort-by=memory       # Sort by memory
kubectl top nodes                       # Node usage
```

### Advanced

```bash
# API resources
kubectl api-resources                   # All available resources
kubectl api-versions                    # All API versions
kubectl explain pod.spec.containers     # YAML field docs

# JSONPath
kubectl get pods -o jsonpath='{.items[*].metadata.name}'
kubectl get pods -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.phase}{"\n"}{end}'

# Custom columns
kubectl get pods -o custom-columns=NAME:.metadata.name,NODE:.spec.nodeName,STATUS:.status.phase

# Dry run
kubectl apply -f manifest.yaml --dry-run=client  # Client-side validation
kubectl apply -f manifest.yaml --dry-run=server  # Server-side validation

# Diff
kubectl diff -f manifest.yaml          # Show what would change

# Raw API
kubectl get --raw /api/v1/pods         # Direct API call
kubectl get --raw /apis/apps/v1/deployments
```

---

## 4. kind / k3d Quick Reference

### kind

```bash
# Install
go install sigs.k8s.io/kind@latest
# brew install kind
# choco install kind

# Create cluster
kind create cluster --name my-cluster

# Multi-node cluster
cat > kind-config.yaml << 'EOF'
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
  - role: worker
  - role: worker
EOF
kind create cluster --config kind-config.yaml

# With port mapping (access services from host)
cat > kind-with-ports.yaml << 'EOF'
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    extraPortMappings:
      - containerPort: 30000
        hostPort: 30000
        protocol: TCP
  - role: worker
  - role: worker
EOF

# List clusters
kind get clusters

# Get kubeconfig
kind get kubeconfig --name my-cluster

# Load local image (bypass registry)
kind load docker-image myapp:v1 --name my-cluster

# Delete cluster
kind delete cluster --name my-cluster

# Delete all clusters
kind delete clusters --all
```

### k3d (k3s in Docker)

```bash
# Install
curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash

# Create cluster
k3d cluster create my-cluster

# Multi-node
k3d cluster create my-cluster --servers 1 --agents 2

# With port mapping
k3d cluster create my-cluster -p "8080:80@loadbalancer"

# Import image
k3d image import myapp:v1 -c my-cluster

# List
k3d cluster list

# Delete
k3d cluster delete my-cluster
```

---

## 5. Object Lifecycle State Diagram

```
Pod Lifecycle:
                    ┌─────────┐
                    │ Created  │
                    │ (API)    │
                    └────┬────┘
                         │
               ┌─────────▼─────────┐
               │     Pending       │
               │                   │
               │ • Waiting schedule │
               │ • Pulling image   │
               │ • Init containers │
               └────────┬──────────┘
                        │
              ┌─────────▼──────────┐
              │     Running        │
              │                    │
              │ • Containers up    │
              │ • Probes running   │
              │ • Processing       │
              └───┬──────────┬─────┘
                  │          │
       ┌──────────▼┐   ┌────▼────────┐
       │ Succeeded │   │   Failed    │
       │           │   │             │
       │ All done  │   │ Container   │
       │ exit 0    │   │ exit != 0   │
       └───────────┘   └─────────────┘

Container States:
┌──────────┐     ┌──────────┐     ┌────────────┐
│ Waiting  │────▶│ Running  │────▶│ Terminated │
│          │     │          │     │            │
│ • Image  │     │ • Active │     │ • Exit 0   │
│   pull   │     │ • Probes │     │ • Exit >0  │
│ • Init   │     │          │     │ • OOMKill  │
└──────────┘     └──────────┘     └────────────┘
      ▲                                 │
      └───── CrashLoopBackOff ──────────┘
              (restart with backoff)
```

---

## 6. API Request Flow Diagram

```
                     kubectl apply -f deployment.yaml
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│                      API Server                         │
│                                                         │
│  1. Authentication ─── Who are you?                     │
│     ├── x509 client certificate                         │
│     ├── Bearer token                                    │
│     ├── OIDC token                                      │
│     └── Service account token                           │
│                                                         │
│  2. Authorization ──── Can you do this?                 │
│     └── RBAC: Role + RoleBinding                        │
│                                                         │
│  3. Admission Control ─ Should we allow this?           │
│     ├── Mutating webhooks (modify request)              │
│     │   └── e.g., inject sidecar, add labels            │
│     └── Validating webhooks (accept/reject)             │
│         └── e.g., require resource limits               │
│                                                         │
│  4. Validation ──── Is the YAML correct?                │
│     └── Schema validation against OpenAPI spec          │
│                                                         │
│  5. Persist ──── Save to etcd                           │
│     └── Create/Update object in etcd                    │
│                                                         │
│  6. Notify ──── Tell watchers                           │
│     └── Send watch events to controllers/kubelet        │
└─────────────────────────────────────────────────────────┘
```

---

## 7. Troubleshooting Decision Tree

```
Pod not running?
│
├── Phase: Pending
│   ├── Events: "FailedScheduling"
│   │   ├── "Insufficient cpu/memory"
│   │   │   └── Fix: Reduce requests OR add nodes
│   │   ├── "node(s) had taint ... not tolerated"
│   │   │   └── Fix: Add toleration OR remove taint
│   │   ├── "node(s) didn't match node selector"
│   │   │   └── Fix: Correct nodeSelector/affinity
│   │   └── "0/N nodes are available"
│   │       └── Fix: Check all nodes Ready
│   └── Events: "Pulling" (stuck)
│       └── Fix: Check image name, registry auth, network
│
├── Phase: Running but CrashLoopBackOff
│   ├── Exit Code 1: App error
│   │   └── kubectl logs POD --previous → Fix app
│   ├── Exit Code 137: OOMKilled
│   │   └── Increase memory limit
│   ├── Exit Code 143: SIGTERM
│   │   └── Check liveness probe, preStop hook
│   └── Exit Code 0 + restart: wrong CMD
│       └── Fix: CMD should be long-running process
│
├── Phase: ImagePullBackOff
│   ├── "not found": Wrong image name/tag
│   ├── "unauthorized": Missing imagePullSecret
│   └── "timeout": Registry unreachable
│
├── Phase: Running but not ready
│   └── Readiness probe failing
│       ├── App not ready yet → Increase initialDelaySeconds
│       ├── Probe endpoint wrong → Fix path/port
│       └── Dependency not available → Check dependencies
│
└── Phase: Terminating (stuck)
    ├── Finalizers blocking deletion
    │   └── kubectl patch pod POD -p '{"metadata":{"finalizers":null}}'
    └── preStop hook hanging
        └── Check preStop timeout / fix hook
```

---

## 8. etcd Operations Reference

```bash
# Health check
kubectl get --raw /healthz/etcd

# Cluster member list (inside etcd pod)
kubectl exec -n kube-system etcd-NODENAME -- etcdctl \
  --endpoints https://127.0.0.1:2379 \
  --cacert /etc/kubernetes/pki/etcd/ca.crt \
  --cert /etc/kubernetes/pki/etcd/server.crt \
  --key /etc/kubernetes/pki/etcd/server.key \
  member list

# Cluster status
etcdctl endpoint health
etcdctl endpoint status --write-out=table

# Key count
etcdctl get / --prefix --keys-only | wc -l

# Backup
etcdctl snapshot save /backup/etcd-snapshot.db

# Restore
etcdctl snapshot restore /backup/etcd-snapshot.db \
  --data-dir=/var/lib/etcd-restored

# Compaction (reclaim space)
etcdctl compact $(etcdctl endpoint status --write-out=json | jq '.[0].Status.header.revision')

# Defrag
etcdctl defrag
```

---

## 9. Quick Reference Cards

### Pod Debugging Flowchart

```bash
# Step 1: What's the status?
kubectl get pod POD_NAME -o wide

# Step 2: What do events say?
kubectl describe pod POD_NAME | tail -20

# Step 3: What do logs say?
kubectl logs POD_NAME
kubectl logs POD_NAME --previous    # if crashing

# Step 4: Can I exec into it?
kubectl exec -it POD_NAME -- sh

# Step 5: What's the node status?
kubectl describe node $(kubectl get pod POD_NAME -o jsonpath='{.spec.nodeName}')
```

### Resource Quick Reference

| Resource | Short | API Group | Namespaced |
|----------|-------|-----------|-----------|
| pods | po | v1 | Yes |
| services | svc | v1 | Yes |
| deployments | deploy | apps/v1 | Yes |
| replicasets | rs | apps/v1 | Yes |
| statefulsets | sts | apps/v1 | Yes |
| daemonsets | ds | apps/v1 | Yes |
| jobs | — | batch/v1 | Yes |
| cronjobs | cj | batch/v1 | Yes |
| configmaps | cm | v1 | Yes |
| secrets | — | v1 | Yes |
| nodes | no | v1 | No |
| namespaces | ns | v1 | No |
| persistentvolumes | pv | v1 | No |
| persistentvolumeclaims | pvc | v1 | Yes |
| ingresses | ing | networking.k8s.io/v1 | Yes |
| networkpolicies | netpol | networking.k8s.io/v1 | Yes |

