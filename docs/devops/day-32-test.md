# Test

<details>

<summary>Solution</summary>

### Quality Gate Matrix

| Gate | Critical Service | High Service | Medium/Low Service |
|------|-----------------|-------------|-------------------|
| **Lint** | ❌ Block on any issue | ❌ Block on errors | ⚠️ Warning only |
| **Unit Test Coverage** | ❌ Block < 80% | ❌ Block < 70% | ❌ Block < 50% |
| **Integration Tests** | ❌ Must pass all | ❌ Must pass all | ⚠️ Warning on fail |
| **CRITICAL CVE** | ❌ Block (zero tolerance) | ❌ Block | ⚠️ Block with 48h exception |
| **HIGH CVE** | ❌ Block (fix within 7 days) | ⚠️ Warning (fix within 14 days) | ⚠️ Warning (fix within 30 days) |
| **Secret scan** | ❌ Block | ❌ Block | ❌ Block |
| **Image size** | ⚠️ Warning > 100MB | ⚠️ Warning > 200MB | Info only |
| **Performance test** | ❌ Block on regression > 10% | ⚠️ Warning on regression | Not required |
| **Manual approval (prod)** | ✅ Required (2 approvers) | ✅ Required (1 approver) | Auto-deploy |

### Approval Flow

PR Merged to main

test

</details>
