# DR Runbook, DR Checklist & Final Demo Script
## Capstone Production-Grade — Day 35 Reference

---

## Part A: DR Runbook Template

### DR Runbook Structure

```
RUNBOOK-{INCIDENT_TYPE}
==============================================
Severity:     P1 / P2 / P3 / P4
RTO Target:  X phút
RPO Target:  X phút
Owner:       Platform / DevOps
Last Tested: YYYY-MM-DD

INCIDENT DETECTION
------------------
Symptoms:
  - ...

DIAGNOSTIC CHECKLIST
--------------------
□ Step 1: ...
□ Step 2: ...

IMMEDIATE ACTIONS (first 5 minutes)
----------------------------------
1. ...

ROOT CAUSE IDENTIFICATION
------------------------
□ Verify: ...
□ Check logs: ...

ROLLBACK / RECOVERY STEPS
-------------------------
1. ...

POST-INCIDENT
-------------
□ Document in incident tracker
□ Notify stakeholders
□ Write postmortem (within 48h)
□ Update this runbook if gaps found

PREVENTION
----------
□ ...
```

---

## Part B: DR Scenarios — Full Runbook

### RUNBOOK-01: Cluster Loss (EKS Deleted / Kind Cluster Deleted)

```
Severity:     P1 (Full outage)
RTO Target:  15-30 phút (Mode B) / 5 phút (Mode A kind)
RPO Target:  0 phút (stateless app) / 15 phút (stateful app)
Owner:       Platform Engineer

INCIDENT DETECTION
------------------
Symptoms:
  - kubectl timeout: "The connection to the server was refused"
  - ArgoCD dashboard not accessible
  - AWS Console: EKS cluster shows "DELETED" status

DIAGNOSTIC CHECKLIST
--------------------
□ 1. Verify cluster deleted:
     aws eks describe-cluster --name capstone-dev --region eu-west-1
     # Expected: ClusterNotFoundException
□ 2. Check if it's Terraform-managed:
     aws ec2 describe-vpcs --filters Name=tag:Project,Values=capstone
     # If VPC still exists → cluster lost, not full account compromise
□ 3. Check billing impact:
     aws ce get-cost-and-usage \
       --time-period Start=$(date -d '7 days ago' +%Y-%m-%d),End=$(date +%Y-%m-%d) \
       --granularity DAILY \
       --metrics BlendedCost
□ 4. Verify Git repos accessible:
     git -C ~/capstone/capstone-infra remote -v
     git -C ~/capstone/capstone-platform remote -v
     git -C ~/capstone/capstone-apps remote -v

IMMEDIATE ACTIONS (first 5 minutes)
-----------------------------------
1. Notify stakeholders: "Capstone production cluster is down. ETA recovery: 15-30 minutes."
2. Stop all active deployments: Disable GitHub Actions workflow triggers
3. Verify Terraform state still intact (S3 bucket has cluster definition)

RECOVERY STEPS
--------------
MODE B (AWS EKS):

Step 1: Verify state integrity
  aws s3 cp s3://capstone-tf-state/terraform.tfstate /tmp/terraform.tfstate
  cd capstone-infra/terraform/envs/prod
  terraform init
  terraform plan 2>&1 | tail -20
  # Verify plan shows EKS cluster recreate, not 50+ resource destruction

Step 2: Restore cluster
  terraform apply -target=module.eks -auto-approve
  # Duration: ~10-15 phút

Step 3: Verify cluster
  aws eks update-kubeconfig --name capstone-dev --region eu-west-1
  kubectl get nodes
  # Expected: All nodes Ready

Step 4: Recreate OIDC provider (ArgoCD IRSA depends on it)
  # terraform-aws-modules/eks/aws handles this automatically via module
  # If manual: aws iam create-open-id-connect-provider --url <OIDC_URL>

Step 5: ArgoCD bootstrap
  kubectl apply -f capstone-platform/bootstrap/root-app.yaml
  argocd admin import - < backups/YYYYMMDD/argocd-backup-full.yaml

Step 6: Wait for all apps synced
  argocd app list
  argocd app wait --all --timeout 600
  # ArgoCD self-heals all apps from Git → ~5-10 phút

Step 7: Verify service health
  kubectl get pods -A | grep -v Running | grep -v Completed
  kubectl get ingress -A

MODE A (kind):

Step 1: Restore kind cluster
  kind delete cluster --name capstone || true
  kind create cluster --config ~/capstone/local/kind-config.yaml

Step 2: ArgoCD reinstall
  kubectl apply -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

Step 3: ArgoCD bootstrap
  argocd login localhost:8080
  kubectl apply -f ~/capstone/capstone-platform/bootstrap/root-app.yaml

Step 4: Verify
  argocd app list | grep -E "Synced|Healthy"

POST-INCIDENT
-------------
□ Update incident tracker: ROOT CAUSE = Terraform destroy nhầm / AZ failure / human error
□ Review: Có prevent_destroy = true trong Terraform không?
□ Review: IAM policy có hạn chế cluster delete không?
□ Update DR matrix: RTO thực tế = X phút
```

---

### RUNBOOK-02: ArgoCD Deleted / CrashLoopBackOff

```
Severity:     P1 (No GitOps control, apps still running)
RTO Target:  10-15 phút
RPO Target:  0 phút (Git as source of truth)
Owner:       Platform Engineer

INCIDENT DETECTION
------------------
Symptoms:
  - argocd CLI: "connection refused"
  - ArgoCD pods: CrashLoopBackOff
  - ArgoCD UI: 502 Bad Gateway
  - Application status: Unknown (vì ArgoCD không query được)

DIAGNOSTIC CHECKLIST
--------------------
□ 1. kubectl get pods -n argocd
     # Xem CrashLoopBackOff reason
□ 2. kubectl logs -n argocd deployment/argocd-server --previous
     # Xem log của container fail trước
□ 3. kubectl describe pod -n argocd <pod-name> | tail -30
     # Xem Events
□ 4. Check storage:
     kubectl get pvc -n argocd
     # PVC missing = common cause of ArgoCD crash
□ 5. Check namespace:
     kubectl get ns argocd
     # Namespace bị delete → full reinstall needed

IMMEDIATE ACTIONS (first 3 minutes)
-----------------------------------
1. DO NOT delete ArgoCD namespace if still exists
2. Identify root cause from diagnostic above
3. If storage issue: restore PVC from backup or recreate storage

RECOVERY STEPS
--------------
SCENARIO A: ArgoCD namespace still exists, pods crash:

Step 1: Check if backup exists
  ls -lh ~/capstone/backups/$(date +%Y%m%d)/argocd-backup-full.yaml

Step 2: Restart ArgoCD without changing config
  kubectl rollout restart deployment argocd-server -n argocd
  kubectl rollout restart deployment argocd-repo-server -n argocd
  kubectl rollout restart deployment argocd-application-controller -n argocd

Step 3: Wait for pods healthy
  kubectl get pods -n argocd -w
  # Ctrl+C when all Running

Step 4: Import backup config
  argocd login argocd.internal --username admin --password $(kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}' | base64 -d)
  argocd admin import - < ~/capstone/backups/$(date +%Y%m%d)/argocd-backup-full.yaml

Step 5: Verify apps reconciled
  argocd app list
  argocd app sync --all  # Force full sync

SCENARIO B: ArgoCD namespace deleted:

Step 1: Recreate namespace + ArgoCD
  kubectl create namespace argocd
  kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

Step 2: Wait ArgoCD ready
  kubectl get pods -n argocd -w
  # Duration: ~3-5 phút

Step 3: Import backup
  argocd login argocd.internal
  argocd admin import - < ~/capstone/backups/$(date +%Y%m%d)/argocd-backup-full.yaml

Step 4: Verify apps
  argocd app list
  # Expected: All apps appear (might need manual sync if auto-sync off)

POST-INCIDENT
-------------
□ Update runbook: Document what caused ArgoCD namespace delete
□ Prevention: Add ArgoCD namespace to protected namespaces in all delete policies
□ Prevention: Schedule daily ArgoCD backup via cron job
□ Test: Verify backup/restore procedure quarterly
```

---

### RUNBOOK-03: Wrong Secret / ESO Sync Failure

```
Severity:     P2 (App degraded, partial outage)
RTO Target:  5-10 phút
RPO Target:  0 phút
Owner:       DevOps / Backend Engineer

INCIDENT DETECTION
------------------
Symptoms:
  - Pod: CrashLoopBackOff với "secret not found" hoặc "authentication failed"
  - ESO: "Sync error" status trong kubectl get externalsecret
  - App health check: 500 Internal Server Error
  - Database connection: "password authentication failed"

DIAGNOSTIC CHECKLIST
--------------------
□ 1. kubectl get pods -n apps | grep -v Running
     # Xem pods fail với lý do gì
□ 2. kubectl describe pod <failing-pod> -n apps | grep -A 10 "Events"
     # Lỗi cụ thể: secret missing hay wrong value
□ 3. kubectl get externalsecret -n apps
     # ESO status: Error / SecretSynced / Unknown
□ 4. kubectl get externalsecret <name> -n apps -o yaml | kubectl neat
     # Xem ESO configuration
□ 5. aws secretsmanager list-secrets --filter Key=name,Values=capstone
     # Verify secret tồn tại trong AWS
□ 6. kubectl get secret <secret-name> -n apps -o yaml
     # Verify secret đã sync, xem value có đúng không

IMMEDIATE ACTIONS (first 3 minutes)
------------------------------------
1. Identify which secret is wrong: db-password / api-key / redis-password
2. If production down: trigger immediate ESO sync first (fastest fix)
3. If ESO sync fails: check AWS Secrets Manager (manual fallback)

RECOVERY STEPS
--------------
STEP 1: Force ESO sync (fastest, automated)
  # Annotate force-sync
  SECRET_NAME=$(kubectl get externalsecret -n apps -o jsonpath='{.items[0].metadata.name}')
  kubectl annotate externalsecret $SECRET_NAME -n apps \
    force-sync=$(date +%s) --overwrite

  # Wait for sync
  sleep 30
  kubectl get externalsecret -n apps

STEP 2: If ESO still failing, check AWS Secrets Manager
  # Verify secret exists and has correct key
  aws secretsmanager get-secret-value \
    --secret-id capstone/db-password \
    --query SecretString --output text

STEP 3: If AWS secret wrong, update it
  aws secretsmanager put-secret-value \
    --secret-id capstone/db-password \
    --secret-string "correct-password-here"

  # Then force ESO sync again
  kubectl annotate externalsecret $SECRET_NAME -n apps \
    force-sync=$(date +%s) --overwrite

STEP 4: If ESO completely down, manual secret creation
  # TEMPORARY FALLBACK ONLY — fix ESO sau
  kubectl create secret generic db-password \
    -n apps \
    --from-literal=password="correct-password" \
    --dry-run=client -o yaml | kubectl apply -f -

STEP 5: Restart affected deployments
  kubectl rollout restart deployment api-service -n apps
  kubectl rollout restart deployment worker-service -n apps

STEP 6: Verify
  kubectl get pods -n apps -l app=api-service
  curl http://api-service.internal/health

PREVENTION
----------
□ ESO refreshInterval: 1h hoặc thấp hơn cho production
□ Alert khi ESO ở Error state > 5 phút
□ Test secret rotation trong staging trước production
□ Audit log: AWS CloudTrail log khi secret được access/modify
```

---

### RUNBOOK-04: Bad Deployment / Cascade Failure

```
Severity:     P2 (Production degraded, user impact)
RTO Target:  3-5 phút
RPO Target:  0 phút (stateless app)
Owner:       Backend + Platform Engineer

INCIDENT DETECTION
------------------
Symptoms:
  - ArgoCD: Sync thành công nhưng Health: Degraded
  - Pod: CrashLoopBackOff / OOMKilled / ImagePullBackOff
  - Service: 503 / 500 response
  - User complaints: specific feature broken

DIAGNOSTIC CHECKLIST
--------------------
□ 1. argocd app get api-service
     # Show sync status + health status
□ 2. kubectl get pods -n apps -l app=api-service
     # Xem pods đang fail
□ 3. kubectl describe deployment api-service -n apps | tail -20
     # Xem Events
□ 4. kubectl logs <failing-pod> -n apps --previous
     # Xem logs của container fail
□ 5. argocd app diff api-service
     # Xem diff so với Git

IMMEDIATE ACTIONS (first 3 minutes)
----------------------------------
DO NOT DEBUG. ROLLBACK FIRST.

1. argocd app rollback api-service
2. Notify team: "Rolling back api-service to previous version. ETA: 2 minutes."
3. Investigate root cause WHILE rollback đang chạy

ROLLBACK STEPS
--------------
STEP 1: Quick rollback (ArgoCD)
  argocd app rollback api-service
  argocd app wait api-service --timeout 120

  # Hoặc rollback về specific revision:
  # argocd app sync api-service --revision <revision-id>

STEP 2: Verify rollback
  argocd app get api-service
  kubectl get pods -n apps -l app=api-service

STEP 3: If Argo Rollouts (canary):
  kubectl argo rollouts abort api-service
  kubectl argo rollouts undo api-service
  kubectl argo rollouts get api-service

STEP 4: Service health check
  curl http://api-service.internal/health
  # Expected: HTTP 200 + {"status":"healthy"}

STEP 5: Notify stakeholders rollback complete

POST-INCIDENT
-------------
□ Review diff: `argocd app diff api-service --revision <bad-revision>`
□ Identify root cause: bad image tag / wrong env var / resource limit / breaking change
□ Create fix PR
□ Test in staging trước khi re-promote
□ Update CI/CD pipeline: thêm pre-production validation nếu thiếu
```

---

### RUNBOOK-05: Terraform State Lock / Corruption

```
Severity:     P1 (Cannot apply infrastructure changes)
RTO Target:  5-30 phút (tùy scenario)
RPO Target:  Varies (phụ thuộc backup gần nhất)
Owner:       Platform Engineer

INCIDENT DETECTION
------------------
Symptoms:
  - terraform apply: "Error acquiring the state lock"
  - terraform plan: "state file does not exist"
  - terraform apply: "Provider produced inconsistent final plan"

DIAGNOSTIC CHECKLIST
--------------------
□ 1. Check lock status:
     aws dynamodb get-item \
       --table-name capstone-tf-locks \
       --key '{"LockID": {"S": "<lock-id>"}}'
     # Xem ai đang hold lock + thời gian
□ 2. Check S3 bucket accessible:
     aws s3 ls s3://capstone-tf-state/
□ 3. Check state file exists:
     aws s3 ls s3://capstone-tf-state/terraform.tfstate
□ 4. Check S3 versioning (có backup không):
     aws s3api list-object-versions \
       --bucket capstone-tf-state \
       --prefix terraform.tfstate \
       --query 'Versions[0:3]'

IMMEDIATE ACTIONS
-----------------
IF STATE LOCKED:
  1. Try force-unlock: terraform force-unlock <LOCK_ID>
  2. If fails (lock ID unknown): aws dynamodb delete-item --table-name capstone-tf-locks --key ...

IF STATE CORRUPTED/MISSING:
  1. Stop all Terraform operations immediately
  2. Restore from S3 versioning

RECOVERY STEPS
--------------
STEP 1: Force unlock (if lock ID known):
  cd capstone-infra/terraform/envs/dev
  terraform force-unlock <LOCK_ID>

STEP 2: If lock ID unknown, delete lock directly:
  LOCK_ID="capstone-dev-$(aws sts get-caller-identity --query Account --output text)-terraform.tfstate"
  aws dynamodb delete-item \
    --table-name capstone-tf-locks \
    --key "{\"LockID\": {\"S\": \"$LOCK_ID\"}}"

STEP 3: Restore state from S3 (if corrupted/missing):
  # Get latest version
  aws s3api list-object-versions \
    --bucket capstone-tf-state \
    --prefix terraform.tfstate \
    --query 'Versions[0].VersionId' --output text
  # Output: <version-id>

  # Restore
  aws s3 cp s3://capstone-tf-state/terraform.tfstate \
    /tmp/terraform.tfstate.$(date +%Y%m%d) \
    --version-id <version-id>

  # Push to state
  cd capstone-infra/terraform/envs/dev
  terraform init
  terraform state push /tmp/terraform.tfstate.$(date +%Y%m%d)

STEP 4: Verify state healthy:
  terraform plan | tail -5
  # Expected: No changes (refreshed) or small diff

STEP 5: If state completely lost (no S3 version):
  # LAST RESORT: terraform import resources
  # Step-by-step:
  # 1. List resources từ AWS Console
  # 2. terraform import <resource_type>.<name> <aws_resource_id>
  # 3. terraform plan để verify

PREVENTION
----------
□ Always: terraform init → terraform state pull → terraform plan
□ Never: disable state locking
□ Daily: aws s3 cp s3://bucket/terraform.tfstate ./backups/
□ Terraform Cloud / Vault backend = better locking UX
□ Pipeline: state operations must complete before next step
□ Alert: CloudWatch alarm khi DynamoDB lock > 10 phút
```

---

### RUNBOOK-06: Rollback Application (Ongoing Incident)

```
Severity:     P2 (Active user impact)
RTO Target:  3 phút
RPO Target:  0 phút
Owner:       Backend + Platform Engineer

IMMEDIATE ACTIONS (first 2 minutes)
------------------------------------
1. Notify #incidents channel: "Rolling back api-service. ETA: 2 minutes."
2. argocd app rollback api-service --skip-confirmation

RECOVERY STEPS
--------------
STEP 1: Identify rollback target
  argocd app history api-service
  # Chọn revision trước đó (thường là revision N-1)

STEP 2: Execute rollback
  argocd app rollback api-service

STEP 3: Wait for health
  argocd app wait api-service --timeout 120

STEP 4: Verify service restored
  curl http://api-service.internal/health
  kubectl get pods -n apps -l app=api-service

STEP 5: If Argo Rollouts canary:
  kubectl argo rollouts abort api-service
  kubectl argo rollouts get api-service

STEP 6: Confirm to stakeholders
  Message: "api-service rolled back to v{prev}. Service restored. Investigating v{current} issue."

POST-INCIDENT
-------------
□ Create issue: "api-service v{current} causes X, rolled back to v{prev}"
□ Tag: severity/p2, type/regression
□ Root cause analysis trước khi re-promote
□ CI/CD: thêm automated smoke test trước promote
```

---

## Part C: DR Checklist

### Daily DR Checklist

```
DR DAILY CHECK (5 phút mỗi ngày làm việc)
==========================================

BACKUP STATUS
-------------
□ ArgoCD backup exists (within 24h):
    ls -lh ~/capstone/backups/$(date +%Y%m%d | head -c 6)*/argocd-backup-full.yaml
□ Terraform state backup exists (within 24h):
    aws s3 ls s3://capstone-tf-state/ | grep tfstate | tail -1
□ S3 bucket versioning enabled:
    aws s3api get-bucket-versioning --bucket capstone-tf-state | grep Status
□ Database backup (RDS automated):
    aws rds describe-db-instance-backups \
      --db-instance-identifier capstone-db \
      --query 'DBBackupList[0].BackupRetentionPeriod'

CLUSTER HEALTH
--------------
□ All nodes Ready:
    kubectl get nodes
□ All pods Running (không CrashLoopBackOff):
    kubectl get pods -A | grep -v Running | grep -v Completed | wc -l
    # Expected: 0
□ ArgoCD apps all Synced + Healthy:
    argocd app list | grep -v Synced | grep -v Healthy
    # Expected: (empty)

SECRETS HEALTH
--------------
□ ESO synced (no Error status):
    kubectl get externalsecret -A | grep Error
    # Expected: (empty)
□ No pod crash vì secret:
    kubectl get events -A | grep -i "secret.*not\|auth.*fail"
    # Expected: (empty)

TERRAFORM STATE
--------------
□ State lock available:
    cd capstone-infra/terraform/envs/dev
    terraform init
    terraform plan 2>&1 | tail -3
    # Expected: "Refreshing..." thành công, không lock error
□ State file size reasonable:
    aws s3 ls s3://capstone-tf-state/terraform.tfstate --summarize
    # Compare với yesterday: tăng quá nhiều → potential terraform issue
```

### Weekly DR Checklist

```
DR WEEKLY CHECK (30 phút mỗi tuần)
==================================

TESTS
-----
□ Test ArgoCD backup restore (staging env):
    argocd admin import - < backups/latest/argocd-backup-full.yaml
    argocd app list
□ Test RDS restore (staging RDS snapshot → new instance):
    aws rds restore-db-instance-from-db-snapshot \
      --db-instance-identifier capstone-db-restore-test \
      --snapshot-identifier rds:capstone-db-automated-backup-$(date +%Y%m%d) \
      --db-instance-class db.t3.micro
□ Test Terraform state restore:
    aws s3 cp s3://capstone-tf-state/terraform.tfstate /tmp/test-restore.tfstate
    # Verify file is valid JSON/HCL

DOCUMENTATION
-------------
□ Runbook updated (nếu có incident trong tuần)
□ DR matrix RTO/RPO accurate?
□ Contact list updated?

ALERTS
------
□ Verify alert rules still active:
    kubectl get prometheusrule -A | grep -v "argocd-argocd"
□ Test PagerDuty/Slack alert:
    curl -X POST https://hooks.slack.com/... -d '{"text":"DR weekly test"}'
□ Verify budget alert:
    aws budgets describe-budgets --account-id <AWS_ACCOUNT>
```

### Monthly GameDay Checklist

```
DR GAMEDAY (2-4 giờ mỗi tháng)
===============================

PHASE 1: PREPARATION (30 phút)
-------------------------------
□ Notify team: "GameDay scheduled, expected downtime: 30 phút"
□ Backup everything trước khi bắt đầu
□ Verify backup integrity
□ Set up monitoring dashboard (Grafana)
□ Define success criteria: RTO < X, RPO < Y

PHASE 2: INCIDENT SIMULATION (60-90 phút)
------------------------------------------
Chọn 2-3 scenario từ:
□ Scenario 1: ArgoCD app delete → restore (Part 2 lab)
□ Scenario 2: Bad deployment → rollback (Part 3 lab)
□ Scenario 3: Simulate cluster node failure
□ Scenario 4: Simulate database connection failure (ESO secret wrong)
□ Scenario 5: Terraform state lock (terraform apply đang chạy, interrupt)

PHASE 3: MEASUREMENT (15 phút)
-------------------------------
Record:
  □ Incident start time: T1
  □ Detection time: T2
  □ Recovery time: T3
  □ RTO achieved: T3 - T1 = X phút
  □ Data loss: Y phút

PHASE 4: RETROSPECTIVE (30 phút)
---------------------------------
□ What went well?
□ What needs improvement?
□ Action items: Update runbook / fix tooling / training
□ Next GameDay date: +1 month
```

---

## Part D: Final Demo Script

### Final Demo — End-to-End Platform Walkthrough

```
FINAL DEMO SCRIPT
=================
Audience:     Hiring manager / Team lead / Portfolio viewer
Duration:     10-15 phút
Prereq:       Mode A kind cluster running, apps deployed via ArgoCD

DEMO FLOW
=========

[0:00-0:30] INTRODUCTION
------------------------
"Trong 5 tuần qua, tôi đã xây dựng một production-grade GitOps platform
từ zero: Terraform infrastructure + Ansible configuration + ArgoCD GitOps
+ CI/CD pipeline + Observability + Disaster Recovery."

Architecture overview (chỉ vào diagram):
- Layer 1: Network (VPC, subnets, security groups)
- Layer 2: Kubernetes (EKS/kind, IRSA, ECR/GHCR)
- Layer 3: Data (PostgreSQL, Redis, ESO)
- Layer 4: Platform (ArgoCD, Prometheus, Ingress)
- Layer 5: Apps (3 microservices, GitOps deployment)

[0:30-2:00] GITOPS WORKFLOW
---------------------------
Show how a code change becomes a running deployment:

1. Show GitOps repo structure:
   git -C capstone-apps log --oneline -3
   ls capstone-apps/apps/

2. Show ArgoCD dashboard (CLI):
   argocd app list
   argocd app get api-service

3. Simulate a change:
   # Show current version
   argocd app history api-service
   kubectl get deployment api-service -n apps -o jsonpath='{.spec.template.spec.containers[0].image}'

   # Describe the promotion workflow:
   # dev: auto-sync on commit
   # staging: PR-gated (show GitHub Actions PR check)
   # prod: manual approval

4. Show self-heal:
   kubectl delete pod -n apps -l app=api-service --grace-period=0
   # Pod tự recreate
   kubectl get pods -n apps -l app=api-service

[2:00-3:30] OBSERVABILITY
-------------------------
1. Show Prometheus metrics:
   kubectl port-forward svc/prometheus-stack-kube-prome-prometheus 9090:9090 &
   # (open browser if demo environment)

2. Show ArgoCD metrics:
   kubectl get --raw /api/v1/namespaces/argocd/metrics | head -20

3. Show logging (if Loki available):
   # kubectl logs -n apps deployment/api-service --tail=20

4. Show alert rules:
   kubectl get prometheusrule -n monitoring -o jsonpath='{.items[*].spec.groups[*].rules[*].alert}' | tr ' ' '\n' | grep -v '^$'

[3:30-5:30] DISASTER RECOVERY
-----------------------------
1. Show DR backup:
   ls -lh ~/capstone/backups/$(date +%Y%m%d)/

2. Show runbook:
   cat docs/runbook.md | head -50

3. Demo: ArgoCD app delete + restore:
   argocd app delete api-service
   # Show: cluster resources still running
   kubectl get deployment api-service -n apps
   # Restore
   kubectl apply -f capstone-platform/apps/api-service/application.yaml
   argocd app wait api-service --timeout 120
   argocd app get api-service

4. Demo: Rollback:
   argocd app history api-service
   argocd app rollback api-service
   argocd app get api-service

[5:30-7:00] CI/CD PIPELINE
---------------------------
1. Show GitHub Actions workflow:
   cat .github/workflows/build.yml | head -40

2. Show image promotion:
   gh run list --limit 3

3. Show ArgoCD image updater (nếu có):
   argocd image-updater list

4. Explain: CI/CD là "build once, deploy everywhere" → GitOps là "deploy from Git"

[7:00-8:30] RELIABILITY FEATURES
--------------------------------
1. Readiness/Liveness probes:
   kubectl get deployment api-service -n apps -o yaml | grep -A 10 "readinessProbe"

2. Resource limits:
   kubectl get deployment api-service -n apps -o yaml | grep -A 5 "resources:"

3. HPA (if configured):
   kubectl get hpa -A

4. PodDisruptionBudget:
   kubectl get pdb -A

5. Argo Rollouts canary (nếu có):
   kubectl argo rollouts get api-service

[8:30-10:00] TERRAFORM INFRASTRUCTURE
-------------------------------------
1. Show infrastructure-as-code:
   ls capstone-infra/terraform/modules/

2. Show Terraform state:
   cd capstone-infra/terraform/envs/dev
   terraform state list | head -20

3. Show plan output:
   terraform plan -out=tfplan 2>&1 | tail -10

4. Explain: Infrastructure reproducible, version-controlled, reviewable via PR

[10:00-11:00] COST & SECURITY
-----------------------------
1. Show cost estimate (Mode B):
   # infracost breakdown --path .

2. Show security features:
   - IRSA (no long-lived AWS keys):
     kubectl get serviceaccount -n apps -o jsonpath='{.items[*].metadata.annotations.eks\.amazonaws\.com/role-arn}'
   - ESO (no plain-text secrets in Git)
   - Private RDS:
     aws rds describe-db-instances --query 'DBInstances[*].Endpoint'
   - OIDC (no long-lived GitHub tokens):
     aws iam list-open-id-connect-providers

[11:00-12:00] WRAP-UP
---------------------
Key takeaways:
1. GitOps = single source of truth for deployment (Git)
2. DR = backup (ArgoCD export) + Git-based recovery + tested runbook
3. Infrastructure as Code = reproducible, reviewable, versioned
4. Observability = metrics + logs + alerts = confidence
5. Cost control = always estimate before apply

What's production-ready vs simulation:
- Production-ready: GitOps workflow, ArgoCD rollback, ESO secrets, CI/CD pipeline
- Simulation: kind cluster (vs EKS production), LocalStack (vs real AWS), mock secret store
- Real production additions needed: multi-AZ, real RDS/ElastiCache, production-grade monitoring

Next steps:
1. Migrate from kind to EKS (Day 29-30 outputs)
2. Add real AWS services (RDS, ElastiCache, S3)
3. Multi-region DR
4. Production-grade secrets (HashiCorp Vault, not ESO local provider)
5. Service mesh (Istio) for advanced traffic management
```

---

## Part E: Retrospective Template

### Sprint/Module Retrospective

```
RETROSPECTIVE — CAPSTONE PRODUCTION-GRADE (Day 28-35)
======================================================
Date: 2026-05-15
Duration: 30 phút
Participants: Learner (self-reflection)

FORMAT: Start / Stop / Continue
--------------------------------

WHAT WE STARTED DOING (New habits to keep)
--------------------------------------------
1. ...
2. ...
3. ...

WHAT WE STOPPED DOING (Things that didn't work)
-----------------------------------------------
1. ...
2. ...
3. ...

WHAT WE SHOULD CONTINUE DOING
-----------------------------
1. ...
2. ...
3. ...

PRODUCTION-READY ASSESSMENT
===========================

Infrastructure Layer:
  [x] Terraform module design          - Production-ready
  [ ] Multi-region deployment           - Not implemented (simulation)
  [ ] Terraform state strategy          - Production-ready (S3+DynamoDB)
  [ ] Terraform CI/CD quality gates    - Production-ready

Platform Layer:
  [x] ArgoCD GitOps deployment          - Production-ready
  [ ] ArgoCD multi-cluster              - Not implemented
  [x] ESO secrets management            - Production-ready (ESO+ASM)
  [x] ArgoCD observability              - Production-ready (Prometheus+Grafana)
  [ ] SSO integration (Dex/Okta)       - Not implemented (simulation)

Application Layer:
  [x] 3 microservices deployed          - Production-ready
  [x] CI/CD pipeline (GitHub Actions)   - Production-ready
  [x] Rollback capability               - Production-ready
  [ ] Progressive delivery (canary)     - Partial (Argo Rollouts installed)

Data Layer:
  [ ] PostgreSQL (RDS)                  - Simulation (local Helm chart)
  [ ] Redis (ElastiCache)               - Simulation (local Helm chart)
  [x] Database backup strategy         - Defined but not tested

Operations:
  [x] DR runbook                        - Production-ready
  [x] DR backup procedure               - Production-ready
  [ ] GameDay testing                   - Scheduled (monthly)
  [x] Cost estimation                   - Production-ready

RTO/RPO ACTUAL vs TARGET
========================

Component         | RTO Target | RTO Actual | RPO Target | RPO Actual
-----------------|------------|------------|------------|------------
Cluster (EKS)    | 15 min     | TBD*       | 0 min      | 0 min
ArgoCD           | 10 min     | ~5 min     | 0 min      | 0 min
App deployment   | 3 min      | ~2 min     | 0 min      | 0 min
Terraform state  | 15 min     | TBD*       | varies     | varies
PostgreSQL       | 30 min     | TBD**      | 15 min     | 15 min

* TBD = measure during first real incident or GameDay
** Requires RDS restore test

NEXT STEPS (Priority Order)
===========================

P1 (Critical for production):
  1. Test RDS restore: aws rds restore-db-instance-from-db-snapshot
  2. Add Terraform prevent_destroy for production resources
  3. Configure AWS Budget alert < $50
  4. Test Terraform state restore in isolated environment

P2 (High value):
  5. Set up Argo Rollouts canary for API service
  6. Add Slack/PagerDuty alerting
  7. Configure GitHub Actions OIDC (Day 11 already done)
  8. Add Trivy image scanning to CI/CD pipeline

P3 (Enhancements):
  9. Migrate from ESO local to HashiCorp Vault
  10. Add multi-cluster ArgoCD (EKS staging + EKS prod)
  11. Implement service mesh (Istio)
  12. Add centralized logging (Loki/EFK)

RESOURCES BUILT
===============
GitHub repos:
  - capstone-infra      (Terraform: VPC, EKS, RDS, ElastiCache)
  - capstone-platform   (Helm charts: ArgoCD, ESO, Ingress, Prometheus)
  - capstone-apps       (3 microservices manifests + overlays)
  - capstone-gha        (GitHub Actions CI/CD pipelines)

Documents:
  - docs/architecture.md        (ASCII architecture diagram)
  - docs/cost-estimate.md       (AWS cost breakdown)
  - docs/security-baseline.md    (20-point security checklist)
  - docs/runbook.md             (6 disaster scenarios runbook)
  - docs/final-demo-checklist.md (Demo script)
  - docs/retrospective.md       (This file)

Cost:
  - Mode A: $0 (kind + Docker Compose)
  - Mode B: ~$153-277/tháng (destroy after each session)

LEARNINGS
=========
1. GitOps is the most valuable pattern: app state is always in Git = always recoverable
2. DR is not backup — it's tested recovery procedures with measured RTO/RPO
3. Terraform state is the single point of failure for infrastructure
4. Observability before you need it = debugging 10x faster when you need it
5. Cost control is a feature: always estimate before apply, always destroy after session
```

---

## Part F: Cost & Cleanup Quick Reference

### AWS Cleanup Quick Reference (Mode B)

```bash
# QUICK CLEANUP — RUN THIS AFTER EVERY SESSION
# Estimated time: 10-15 minutes
# Estimated remaining cost if forgotten: $50-200/day

# 1. Terraform destroy (primary)
cd ~/capstone/capstone-infra/terraform/envs/dev
terraform destroy -auto-approve
terraform destroy -auto-approve -target=module.vpc  # If VPC separate

# 2. Verify no resources remain
aws ec2 describe-vpcs --filters Name=tag:Project,Values=capstone --output json | jq '.Vpcs | length'
# Expected: 0

# 3. Check for orphaned resources (RDS snapshots, ECR images)
aws rds describe-db-snapshots --query 'DBSnapshots[?contains(DBInstanceIdentifier,`capstone`)]'
aws ecr describe-repositories --query 'repositories[?contains(repositoryName,`capstone`)]'

# 4. Delete S3 bucket (if empty, if not managed by Terraform)
aws s3 ls | grep capstone
aws s3 rb s3://capstone-tf-state-xxx --force

# 5. Verify AWS Budget
echo "Open: https://console.aws.amazon.com/billing/home#/budgets"
echo "Check: Current spend vs budget limit"

# 6. Cost if forgotten for 1 week:
#    EKS $73 × 7 = $511
#    RDS $15 × 7 = $105
#    ElastiCache $13 × 7 = $91
#    NAT Gateway $32 × 7 = $224
#    Total: ~$931 for 1 week
```

### Mode A Cleanup Quick Reference

```bash
# QUICK CLEANUP — KIND (Mode A)
kind delete clusters
docker system prune -f
rm -rf ~/capstone/backups/
echo "✓ Mode A cleanup complete — 0 cost"
```
