# Day 48: Document — Multi-region, Disaster Recovery Reference

---

## 1. HA vs DR Comparison Matrix

| Tiêu chí | High Availability (HA) | Disaster Recovery (DR) |
|----------|----------------------|----------------------|
| **Mục tiêu** | Giảm downtime cho component failures | Survive khi toàn bộ site/region fail |
| **Scope** | Single region, multi-AZ | Multi-region, multi-DC |
| **Failover time** | Giây → phút (automatic) | Phút → giờ (manual/auto) |
| **Data replication** | Synchronous (same region) | Sync hoặc async (cross-region) |
| **Cost** | 1.5-2x base cost | 2-3x base cost |
| **Complexity** | Medium | High |
| **Testing** | Continuous (built-in) | Periodic (quarterly) |
| **Examples** | K8s pod restart, DB Multi-AZ | Activate DR site |
| **Trigger** | Automatic (health checks) | Manual decision hoặc auto |
| **Data loss risk** | ~0 (sync replication) | 0 → minutes (depends on RPO) |
| **Infrastructure** | Redundant within region | Duplicate across regions |

---

## 2. Active-Active vs Active-Passive Reference

### Active-Passive

```
Normal:
  Region A [ACTIVE]  ←── all traffic
  Region B [PASSIVE] ←── no traffic, standby

Failover:
  Region A [DOWN]
  Region B [ACTIVE]  ←── all traffic (promoted)

Failback:
  Region A [PASSIVE] ←── rebuilt, catching up
  Region B [ACTIVE]  ←── still serving
  ...then switch back
```

**Pros**: Simpler, cheaper, no conflict resolution
**Cons**: DR region idle (wasted cost), failover delay, cold cache

### Active-Active

```
Normal:
  Region A [ACTIVE] ←── US/Americas traffic
  Region B [ACTIVE] ←── EU/EMEA traffic
  Region C [ACTIVE] ←── APAC traffic

Region A fails:
  Region A [DOWN]
  Region B [ACTIVE] ←── US + EU traffic (absorb)
  Region C [ACTIVE] ←── APAC traffic
```

**Pros**: No wasted capacity, lower latency (geo-routing), instant failover
**Cons**: Data consistency complex, conflict resolution needed, 2-3x cost always

### Decision Matrix

| Factor | Active-Passive | Active-Active |
|--------|---------------|---------------|
| **Users** | Single region | Global |
| **SLA target** | 99.95% | 99.99%+ |
| **Write pattern** | Single writer OK | Multi-writer needed |
| **Budget** | 1.5-2x | 2-3x |
| **Team expertise** | Medium | High |
| **Data complexity** | Low | High (conflicts) |
| **Latency requirement** | Region-level OK | < 100ms global |

---

## 3. RPO/RTO Calculation Worksheet

### Per-service Template

```markdown
## Service: [name]

### Data Classification
- Type: [transactional / user-generated / derived / cache / logs]
- Volume: [GB/TB]
- Growth rate: [GB/month]
- Can rebuild?: [yes/no/partial]
- Regulatory?: [GDPR/PCI/HIPAA/none]

### RPO Analysis
- Business impact of data loss: [$X per hour of lost data]
- Minimum acceptable RPO: [0 / 1min / 5min / 1h / 24h]
- Justification: [why this RPO]

### RTO Analysis  
- Business impact per minute of downtime: [$X]
- User tolerance: [minutes users will wait]
- Minimum acceptable RTO: [0 / 5min / 15min / 1h / 4h]
- Justification: [why this RTO]

### Backup Strategy
- Method: [sync replication / async replication / WAL archive / scheduled backup / snapshot]
- Frequency: [continuous / hourly / daily]
- Retention: [7d / 30d / 1y]
- Location: [cross-region S3 / cross-account / tape]
- Encryption: [AES-256 / KMS]

### Recovery Procedure
- Estimated recovery time: [X minutes]
- Automation level: [fully auto / semi-auto / manual]
- Dependencies: [list services needed first]
- Verification: [how to verify recovery success]

### Cost
- Backup storage: [$X/month]
- Replication compute: [$X/month]
- Network transfer: [$X/month]
- Total DR cost for this service: [$X/month]
```

### Common RPO/RTO Targets

| SLA | Downtime/year | Downtime/month | Typical RPO | Typical RTO |
|-----|---------------|----------------|-------------|-------------|
| 99% | 3.65 days | 7.3 hours | 24h | 4h |
| 99.9% | 8.76 hours | 43.8 min | 1h | 1h |
| 99.95% | 4.38 hours | 21.9 min | 15min | 30min |
| 99.99% | 52.6 min | 4.38 min | 1min | 5min |
| 99.999% | 5.26 min | 26.3 sec | 0 | < 1min |

---

## 4. DR Testing Runbook Template

```markdown
# DR Test Runbook — [Platform Name]

## Test Information
- **Date**: YYYY-MM-DD
- **Type**: [Tabletop / Partial / Full]
- **Scope**: [Database only / Full platform / Specific service]
- **Participants**: [names and roles]
- **Duration**: [estimated hours]

## Pre-test Checklist
- [ ] All participants notified and available
- [ ] Monitoring dashboards prepared
- [ ] Communication channel open (#dr-test)
- [ ] Backup verified current (< 1 hour old)
- [ ] Replication lag acceptable (< threshold)
- [ ] Rollback plan documented
- [ ] Customer notification prepared (if needed)

## Test Scenarios

### Scenario 1: Database Failover
- **Action**: Promote DR database replica
- **Expected**: New primary accepting writes within RTO
- **Verify**: INSERT test record, SELECT from new primary
- **Rollback**: Re-establish replication from new primary

### Scenario 2: Application Failover  
- **Action**: Scale DR applications, switch DNS
- **Expected**: All services healthy within RTO
- **Verify**: End-to-end health check, test transaction
- **Rollback**: Switch DNS back, scale down DR

### Scenario 3: Full Platform Failover
- **Action**: Complete DR activation procedure
- **Expected**: Platform fully operational from DR
- **Verify**: Complete user journey test
- **Rollback**: Failback to primary

## Success Criteria
| Metric | Target | Actual | Pass? |
|--------|--------|--------|-------|
| Database failover time | < X min | | |
| Application ready time | < X min | | |
| DNS propagation time | < X min | | |
| Data loss (rows) | 0 | | |
| End-to-end test | Pass | | |
| Total RTO | < X min | | |

## Post-test Actions
- [ ] Document actual RTO achieved
- [ ] Record issues encountered
- [ ] Update runbook with lessons learned
- [ ] Plan remediation for gaps found
- [ ] Schedule next test date
- [ ] Report to stakeholders

## Test Report
### Summary
[1-2 sentence result]

### Issues Found
1. [Issue description + severity + owner]
2. ...

### Improvements Identified
1. [Improvement + priority + owner + deadline]
2. ...

### Next Test
- Date: YYYY-MM-DD
- Scope: [expanded scope if applicable]
```

---

## 5. DNS Failover Configuration Patterns

### Route 53 Health Check + Failover

```bash
# Create health check
aws route53 create-health-check --caller-reference "primary-$(date +%s)" \
  --health-check-config '{
    "IPAddress": "PRIMARY_LB_IP",
    "Port": 443,
    "Type": "HTTPS",
    "ResourcePath": "/health",
    "FullyQualifiedDomainName": "api.example.com",
    "RequestInterval": 10,
    "FailureThreshold": 3
  }'

# Primary record (failover routing)
aws route53 change-resource-record-sets --hosted-zone-id ZONE_ID \
  --change-batch '{
    "Changes": [{
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "api.example.com",
        "Type": "A",
        "SetIdentifier": "primary",
        "Failover": "PRIMARY",
        "TTL": 60,
        "ResourceRecords": [{"Value": "PRIMARY_IP"}],
        "HealthCheckId": "HEALTH_CHECK_ID"
      }
    }]
  }'

# Secondary record (DR)
aws route53 change-resource-record-sets --hosted-zone-id ZONE_ID \
  --change-batch '{
    "Changes": [{
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "api.example.com",
        "Type": "A",
        "SetIdentifier": "secondary",
        "Failover": "SECONDARY",
        "TTL": 60,
        "ResourceRecords": [{"Value": "DR_IP"}]
      }
    }]
  }'
```

### CloudFlare Load Balancing (alternative)

```json
{
  "description": "API failover",
  "steering_policy": "failover",
  "default_pools": ["primary-pool-id"],
  "fallback_pool": "dr-pool-id",
  "proxied": true,
  "ttl": 60,
  "region_pools": {
    "WNAM": ["primary-pool-id"],
    "ENAM": ["primary-pool-id"]
  }
}
```

---

## 6. Restore Procedure Checklist

### Database Restore (PostgreSQL)

```bash
# 1. Verify backup availability
aws s3 ls s3://backups/pg-cluster/ --recursive | tail -5

# 2. Check backup integrity
pgbackrest info --stanza=main

# 3. Create restore point marker
RESTORE_TO="2024-01-15 14:30:00 UTC"

# 4. Stop application traffic
kubectl scale deploy --all --replicas=0 -n production

# 5. Restore database
# CloudNativePG:
kubectl apply -f - <<EOF
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: pg-restored
  namespace: database
spec:
  instances: 3
  storage:
    size: 100Gi
  bootstrap:
    recovery:
      source: pg-backup
      recoveryTarget:
        targetTime: "$RESTORE_TO"
  externalClusters:
  - name: pg-backup
    barmanObjectStore:
      destinationPath: s3://backups/pg-cluster
      s3Credentials:
        accessKeyId:
          name: s3-creds
          key: ACCESS_KEY_ID
        secretAccessKey:
          name: s3-creds
          key: SECRET_ACCESS_KEY
EOF

# 6. Wait for restore
kubectl wait --for=condition=Ready cluster/pg-restored -n database --timeout=3600s

# 7. Verify data integrity
kubectl exec pg-restored-1 -n database -- psql -U postgres -d appdb -c "
  SELECT count(*) FROM orders;
  SELECT max(created_at) FROM orders;
  -- Verify last transaction matches expected restore point
"

# 8. Update application connection strings
kubectl set env deploy/api -n production \
  DATABASE_HOST=pg-restored-rw.database.svc.cluster.local

# 9. Restart applications
kubectl scale deploy --all --replicas=3 -n production

# 10. Verify end-to-end
curl https://api.example.com/health
```

### Application State Restore

```bash
# Redis (cache) — typically rebuild
kubectl exec deploy/api -n production -- curl -X POST http://localhost:8080/admin/warm-cache

# Kafka — verify consumer group offsets
kubectl exec kafka-0 -n kafka -- kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 --group order-processor --describe

# S3 — verify cross-region replication
aws s3 ls s3://dr-bucket/products/ --region us-west-2 | wc -l
```

---

## 7. Multi-region Cost Analysis Reference

### AWS Cost Comparison (example platform)

```
Single Region (us-east-1):
├── EKS Control Plane:      $73/month
├── EC2 (6 × m5.large):     $554/month
├── RDS (db.r6g.large MA):  $560/month
├── ElastiCache (2 nodes):  $200/month
├── MSK (3 brokers):        $540/month
├── ALB:                    $25/month + data
├── S3:                     $50/month
├── NAT Gateway:            $90/month
├── Data Transfer:          $200/month
└── Total:                  ~$2,292/month

+ Cold DR (backup only):
├── S3 Cross-Region:        $30/month
├── Data Transfer:          $50/month
└── DR Total:               ~$80/month (3.5% extra)

+ Warm Standby:
├── EKS Control Plane:      $73/month
├── EC2 (2 × t3.medium):    $67/month
├── RDS Read Replica:       $280/month
├── ElastiCache (1 node):   $50/month
├── ALB:                    $25/month
├── S3 CRR:                 $30/month
└── DR Total:               ~$525/month (23% extra)

+ Active-Passive (full):
├── EKS Control Plane:      $73/month
├── EC2 (6 × m5.large):     $554/month
├── RDS Read Replica:       $280/month
├── ElastiCache (2 nodes):  $200/month
├── MSK (3 brokers):        $540/month
├── ALB:                    $25/month
└── DR Total:               ~$1,672/month (73% extra)

+ Active-Active (2 regions):
├── Full duplicate region:  $2,292/month
├── Data replication:       $300/month
├── Global Accelerator:     $50/month
└── DR Total:               ~$2,642/month (115% extra)
```

### Cost-Benefit Analysis

```
Revenue: $500K/month = $694/hour

Downtime cost per incident (assumed 4-hour outage):
= $694 × 4 = $2,776

Expected incidents per year without DR: 2-4
Expected annual downtime cost: $5,552 - $11,104

DR investment comparison:
├── Cold DR:     $80 × 12 = $960/year    → ROI if > 1.4 hours saved
├── Warm:        $525 × 12 = $6,300/year → ROI if > 9 hours saved  
├── Active-Pass: $1,672 × 12 = $20K/year → ROI if > 29 hours saved
└── Active-Act:  $2,642 × 12 = $32K/year → ROI if > 46 hours saved

Recommendation for $500K revenue:
→ Warm Standby (best ROI for mid-size)
```

---

## 8. Production DR Checklist

### Pre-disaster Preparation

- [ ] DR plan documented và reviewed quarterly
- [ ] Backup verified (automated daily verification)
- [ ] Replication lag monitored (alert < threshold)
- [ ] DNS failover configured và tested
- [ ] IaC for DR region up-to-date
- [ ] Secrets/certificates available in DR region
- [ ] Communication templates prepared
- [ ] On-call team trained on DR activation
- [ ] DR test completed within last quarter

### During DR Activation

- [ ] Incident declared, IC assigned
- [ ] Primary region confirmed down
- [ ] Stakeholders notified
- [ ] DR activation started (timestamp recorded)
- [ ] Database promoted/restored
- [ ] Applications scaled up
- [ ] DNS failover executed
- [ ] Health checks passing
- [ ] End-to-end test completed
- [ ] Status page updated
- [ ] DR activation completed (timestamp recorded, RTO measured)

### Post-DR (Failback Planning)

- [ ] Primary region recovery assessed
- [ ] Data sync from DR → primary planned
- [ ] Gradual traffic shift planned (not instant)
- [ ] Failback tested in staging
- [ ] Communication to customers about failback
- [ ] Post-incident review scheduled
- [ ] DR plan updated with lessons learned

