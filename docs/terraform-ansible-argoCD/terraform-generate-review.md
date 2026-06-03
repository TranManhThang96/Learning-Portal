# Terraform Generate Review - Full 5-Week Course Review

Ngay thuc hien: 2026-05-20

## Scope

Review da duoc mo rong dung theo yeu cau: toan bo khoa `terraform-ansible-argoCD`, khong chi 5 bai cuoi.

- 5 tuan: Week 1 den Week 5.
- 35 ngay hoc: Day 01 den Day 35.
- 105 file Markdown theo ngay: moi ngay co `lesson.md`, `document.md`, `exercises.md`.
- Cac README theo tuan duoc kiem tra nhu metadata/onboarding cho lesson.

## Cach review

- Kiem tra inventory: day folder, day file, week README.
- Kiem tra cau truc lesson: muc tieu, boi canh, kien thuc nen tang, deep dive/trade-offs, hands-on lab, kiem tra, tom tat, tham khao.
- Kiem tra loi Markdown co kha nang lam hong render, dac biet code fence chua dong.
- Kiem tra stale technical content cho Terraform backend, External Secrets Operator, Argo CD, ApplicationSet, GitOps va Kubernetes manifest examples.
- Uu tien sua loi co kha nang lam lab fail, gay hieu sai ve production practice, hoac dung API/version da cu.

## Findings da sua

1. Day 10 - heading lesson khong khop structure
   - Van de: phan tham khao dung heading cap 3 nen audit lesson khong nhan dien duoc.
   - Da sua: chuan hoa thanh heading cap 2.
   - File: `week-2-terraform-production/day-10-import-refactor-lifecycle/lesson.md`

2. Day 17 - Argo CD install/version content cu
   - Van de: lesson/exercise/README con pin theo Argo CD 2.x va chart cu, khong phu hop de hoc theo toolchain hien tai.
   - Da sua: cap nhat command cai Argo CD len `v3.4.2`, CLI guidance len `v3.4.x`, Helm chart `argo-cd` len `9.5.14`, va giu ghi chu verify chart/app mapping truoc production.
   - Files:
     - `week-3-ansible-argocd-core/README.md`
     - `week-3-ansible-argocd-core/day-17-gitops-argocd-architecture/lesson.md`
     - `week-3-ansible-argocd-core/day-17-gitops-argocd-architecture/exercises.md`

3. Week 3-5 - External Secrets Operator API version cu
   - Van de: mot so vi du van dung beta API cu cua ESO trong khi stable API hien tai la `external-secrets.io/v1`.
   - Da sua: cap nhat manifest sang `external-secrets.io/v1`.
   - Files:
     - `week-3-ansible-argocd-core/day-17-gitops-argocd-architecture/lesson.md`
     - `week-3-ansible-argocd-core/day-19-helm-kustomize-argocd/document.md`
     - `week-4-argocd-advanced/day-24-sync-waves-hooks/document.md`
     - `week-5-capstone/day-28-capstone-architecture/lesson.md`

4. Day 22/23 - ApplicationSet lesson structure chua ro
   - Van de: noi dung co phan nen tang va trade-off nhung heading khong dung pattern chung cua khoa.
   - Da sua: chuan hoa heading de lesson scan va nguoi hoc doc de hon.
   - Files:
     - `week-4-argocd-advanced/day-22-applicationset-basics/lesson.md`
     - `week-4-argocd-advanced/day-23-applicationset-advanced/lesson.md`

5. Day 27 - Argo CD DR reinstall target cu
   - Van de: DR lesson con target install manifest theo Argo CD 2.x.
   - Da sua: cap nhat target revision va reinstall URL len `v3.4.2`.
   - File: `week-4-argocd-advanced/day-27-argocd-observability-dr/lesson.md`

6. Day 24 - image guidance trong hook troubleshooting chua nhat quan
   - Van de: phan pitfalls/troubleshooting khuyen nghi pull policy thay vi xu ly release bang immutable image tag.
   - Da sua: doi guidance sang pin immutable tag, registry immutability, verify registry path va `imagePullSecrets`.
   - Files:
     - `week-4-argocd-advanced/day-24-sync-waves-hooks/lesson.md`
     - `week-4-argocd-advanced/day-24-sync-waves-hooks/document.md`

7. Week 1/3/4 - mutable image tag trong vi du co the copy-paste
   - Van de: mot so lab/example dung mutable image tag trong manifest hoac docker-compose, de tao thoi quen khong deterministic.
   - Da sua: pin tag cho Docker/nginx, LocalStack, hook image, va ApplicationSet demo image.
   - Files:
     - `week-1-terraform-foundations/day-03-providers-resources-data-sources/lesson.md`
     - `week-1-terraform-foundations/day-05-remote-backend/lesson.md`
     - `week-3-ansible-argocd-core/day-17-gitops-argocd-architecture/document.md`
     - `week-4-argocd-advanced/day-22-applicationset-basics/lesson.md`
     - `week-4-argocd-advanced/day-24-sync-waves-hooks/lesson.md`

8. Day 31/32 - ESO apply order va version trong capstone
   - Van de: Day 31 apply `ExternalSecret` truoc khi cai ESO, cluster moi se loi vi CRD chua ton tai; mot so noi dung ESO con dung chart/API cu.
   - Da sua: cai ESO truoc, wait CRD, sau do tao `ClusterSecretStore` fake provider va `ExternalSecret`; cap nhat chart reference sang `2.4.*` va API stable.
   - Files:
     - `week-5-capstone/day-31-data-layer-secrets/lesson.md`
     - `week-5-capstone/day-31-data-layer-secrets/document.md`
     - `week-5-capstone/day-32-platform-bootstrap/lesson.md`
     - `week-5-capstone/day-32-platform-bootstrap/document.md`
     - `week-5-capstone/day-32-platform-bootstrap/exercises.md`

9. Day 33/34 - image tag va pull policy mau thuan production mindset
   - Van de: vi du reliability/promotion con dung mutable image tag va pull policy khong hop voi immutable release practice.
   - Da sua: doi sang immutable tag vi du `a1b2c3d`, `imagePullPolicy: IfNotPresent`, va lam ro registry immutability moi la guardrail chinh.
   - Files:
     - `week-5-capstone/day-33-gitops-apps-promotion/lesson.md`
     - `week-5-capstone/day-33-gitops-apps-promotion/document.md`
     - `week-5-capstone/day-34-cicd-observability-reliability/lesson.md`
     - `week-5-capstone/day-34-cicd-observability-reliability/document.md`

## Observations con lai

- Mot so bai dau khoa viet tieng Viet khong dau. Day la van de consistency/editorial, khong phai loi ky thuat lam lab fail.
- Cac chuoi mutable image tag con lai chi xuat hien trong ngu canh anti-pattern/canh bao, khong phai manifest khuyen nghi copy-paste.
- Cac file `exercises.md` co TODO/placeholders cho hoc vien la co chu y, khong duoc tinh la noi dung thieu.
- Day 13 co nhac AWS trong ngu canh so sanh/chuan bi, nhung khong buoc hoc vien provision cloud resource trong lab do.

## Verification da chay

- Inventory: 35 day directories.
- Inventory: 105 day Markdown files.
- Required lesson sections: pass cho 35 `lesson.md`.
- Markdown code fences: balanced cho 105 day Markdown files.
- Stale pattern scan: khong con legacy ESO beta API trong noi dung khoa hoc.
- Stale pattern scan: khong con Argo CD 2.x install pins trong noi dung khoa hoc.
- Mutable image scan: cac `latest` con lai chi nam trong vi du anti-pattern/canh bao.

## Nguon doi chieu

- Terraform S3 backend official docs: https://developer.hashicorp.com/terraform/language/settings/backends/s3
- Argo CD ApplicationSet official docs: https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/applicationset-specification/
- Argo CD releases: https://github.com/argoproj/argo-cd/releases
- Argo Helm chart index: https://argoproj.github.io/argo-helm/index.yaml
- External Secrets Operator roadmap/docs: https://external-secrets.io/latest/contributing/roadmap/
- External Secrets fake provider docs: https://external-secrets.io/latest/provider/fake/
