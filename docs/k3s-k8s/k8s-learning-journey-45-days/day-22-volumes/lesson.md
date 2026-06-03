# Day 22: Volumes

## Mục tiêu bài học

- Hiểu vì sao filesystem trong container không đủ cho mọi use case.
- Phân biệt lifecycle của container, Pod và volume.
- Biết dùng các volume cơ bản: `emptyDir`, `hostPath`, `configMap`, `secret`, `projected`.
- Hiểu khi nào volume là runtime scratch space, khi nào là config injection, và khi nào cần storage bền vững.
- Nhận diện rủi ro production khi dùng `hostPath` và volume chứa secret.

## Vấn đề cần giải quyết

Container image nên immutable, nhưng application vẫn cần đọc/ghi dữ liệu runtime:

- File tạm trong quá trình xử lý request.
- Cache chia sẻ giữa nhiều container trong cùng Pod.
- Config file được mount từ `ConfigMap`.
- Secret file được mount từ `Secret`.
- Certificate/token được project vào filesystem.
- Data cần tồn tại sau khi container restart.

Nếu chỉ ghi vào container filesystem, dữ liệu mất khi container bị recreate. Nếu cần dữ liệu sống lâu hơn Pod, bạn sẽ cần PV/PVC ở Day 23. Day 22 tập trung vào volume gắn với Pod lifecycle và config/runtime injection.

## Mental Model

```text
Container filesystem
  - thuộc container
  - mất khi container bị recreate

Pod volume
  - được khai báo trong Pod spec
  - mount vào một hoặc nhiều containers
  - lifecycle tùy loại volume

Persistent storage
  - tách khỏi Pod
  - quản qua PV/PVC/StorageClass/CSI
```

Volume trong Pod là "ổ đĩa được Kubernetes gắn vào Pod". Nhưng không phải volume nào cũng persistent.

## Lý thuyết cốt lõi

### Container filesystem không phải nơi lưu state bền vững

Mỗi container có writable layer. Layer này:

- Gắn với lifecycle của container.
- Có thể mất khi container restart/recreate.
- Không được chia sẻ tự nhiên với container khác trong cùng Pod.
- Không nên dùng để lưu dữ liệu quan trọng.

Điều này ổn cho application stateless, nhưng không ổn cho file upload, database data, queue data hoặc cache cần survive Pod restart.

### Pod volume

Pod spec khai báo volume ở `spec.volumes`, container mount volume bằng `volumeMounts`:

```yaml
spec:
  volumes:
  - name: workdir
    emptyDir: {}
  containers:
  - name: app
    volumeMounts:
    - name: workdir
      mountPath: /work
```

Một volume có thể mount vào nhiều containers trong cùng Pod. Đây là nền tảng cho sidecar pattern như:

- App ghi log file, sidecar ship log.
- Init container tạo config, app đọc config.
- App ghi output, sidecar upload output.

### `emptyDir`

`emptyDir` được tạo khi Pod được assign vào node và tồn tại đến khi Pod bị xóa khỏi node. Container restart không xóa `emptyDir`, nhưng Pod reschedule sang node khác sẽ mất dữ liệu.

Use case:

- Scratch space.
- Cache tạm.
- Shared workspace giữa init container và app container.
- Buffer không quan trọng.

Không dùng `emptyDir` cho dữ liệu cần bền vững.

### `emptyDir.medium: Memory`

`emptyDir` có thể dùng memory-backed tmpfs:

```yaml
emptyDir:
  medium: Memory
  sizeLimit: 256Mi
```

Phù hợp cho file tạm nhạy cảm hoặc cần tốc độ. Rủi ro là memory dùng cho volume tính vào memory consumption của Pod/node. Nếu app ghi quá nhiều, Pod có thể bị OOM hoặc node chịu pressure.

### `hostPath`

`hostPath` mount file/directory từ node vào Pod:

```yaml
volumes:
- name: node-logs
  hostPath:
    path: /var/log
    type: Directory
```

Use case hợp lý:

- Node agent đọc log hoặc metrics.
- CNI/CSI/monitoring DaemonSet cần truy cập path trên node.
- Lab cần minh họa node-local storage.

Rủi ro:

- Pod bị ràng buộc vào node cụ thể.
- Dễ tạo security escape nếu mount path nhạy cảm.
- Không portable sang managed Kubernetes hoặc policy chặt.
- Data không đi theo Pod khi reschedule.

Trong production, `hostPath` nên bị hạn chế bằng Pod Security/admission policy và chỉ cho workload hạ tầng đã review.

### `configMap` volume

Mount `ConfigMap` thành file giúp app đọc config như file bình thường:

```yaml
volumes:
- name: app-config
  configMap:
    name: app-config
```

Ưu điểm:

- Tách config khỏi image.
- Có thể mount nhiều key thành nhiều file.
- Update mounted file có thể được kubelet refresh sau một khoảng trễ.

Điểm cần nhớ: nếu app không reload config file, việc ConfigMap thay đổi không tự làm app dùng config mới. Với env var từ ConfigMap, Pod phải restart để nhận giá trị mới.

### `secret` volume

`Secret` volume mount dữ liệu secret thành file. Kubernetes thường mount với permission hạn chế hơn:

```yaml
volumes:
- name: tls
  secret:
    secretName: app-tls
```

Best practices:

- Mount secret chỉ vào container cần dùng.
- Dùng `items` để giới hạn key cần mount.
- Set `defaultMode` phù hợp.
- Không log nội dung secret.
- Không coi Kubernetes Secret mặc định là secret manager production đầy đủ.

### `projected` volume

`projected` gom nhiều nguồn vào một volume:

- `configMap`
- `secret`
- `downwardAPI`
- `serviceAccountToken`

Use case phổ biến:

- App cần config + cert + metadata trong một directory.
- Token ngắn hạn cho service account.
- Sidecar cần đọc metadata Pod/namespace.

### `subPath`

`subPath` mount một file hoặc subdirectory từ volume vào path cụ thể:

```yaml
volumeMounts:
- name: config
  mountPath: /etc/app/app.yaml
  subPath: app.yaml
```

Cẩn thận: mount bằng `subPath` thường không nhận update tự động từ ConfigMap/Secret theo cách mount directory bình thường. Dùng `subPath` khi cần tránh ghi đè toàn bộ directory, nhưng hiểu rõ update behavior.

## Deep dive: Cách hoạt động bên trong

Khi Pod được schedule lên node, `kubelet` chuẩn bị volume trước khi start container. Với `emptyDir`, kubelet tạo directory trên node hoặc tmpfs nếu dùng `medium: Memory`. Với `configMap`/`secret`, kubelet materialize key thành file và refresh theo cơ chế sync/cache, nên update không tức thì. Với `hostPath`, kubelet chỉ bind mount path node vào container; Kubernetes không copy data và không làm path đó portable.

Mount order quan trọng: volume được prepare ở node, sau đó container runtime mount vào container path. Nếu mount path trùng directory đã có trong image, nội dung image tại path đó bị che bởi volume.

## K3s vs Kubernetes chuẩn vs Managed Kubernetes

K3s không thay đổi bản chất Pod volumes. Điểm cần chú ý trong lab:

- Với `k3d`, node là Docker container, nên `hostPath` là path bên trong node container, không phải trực tiếp host OS của bạn.
- K3s có `local-path-provisioner` mặc định cho PVC, nhưng đó là Day 23-24; đừng nhầm với `hostPath` mount trực tiếp.
- `emptyDir` và config/secret volumes là lựa chọn tốt cho lab local vì không phụ thuộc storage driver.

Trên Kubernetes chuẩn và managed Kubernetes, Pod volumes cơ bản hoạt động giống nhau. Khác biệt nằm ở policy: nhiều cluster production bật Pod Security/admission policy để chặn `hostPath` hoặc mount path nhạy cảm. Managed Kubernetes thường không cho bạn SSH/root vào node dễ như lab, nên debug `hostPath` và node filesystem cần dùng events, DaemonSet/debug Pod hoặc tooling provider.

## Trade-offs và Best Practices

### Trade-offs

| Volume type | Khi dùng | Không phù hợp |
|---|---|---|
| `emptyDir` | Scratch/cache tạm, shared workspace trong Pod | Data cần sống lâu hơn Pod |
| `emptyDir.medium: Memory` | File tạm nhanh/nhạy cảm | Workload ghi nhiều, memory limit thấp |
| `configMap`/`secret` | Inject config/secret dạng file | Config cần reload tức thì hoặc secret manager production đầy đủ |
| `projected` | Gom config, secret, token, metadata | Khi cần lifecycle/update behavior khác nhau cho từng nguồn |
| `hostPath` | Node agent, CNI/CSI/log collector, lab node-local | App business thông thường, dữ liệu portable/HA |

### Best Practices

- [ ] Dữ liệu quan trọng không nằm trong container writable layer hoặc `emptyDir`.
- [ ] `emptyDir.sizeLimit` được đặt nếu app có rủi ro ghi nhiều.
- [ ] `hostPath` chỉ dùng cho DaemonSet/node-agent đã review.
- [ ] Config/Secret mount chỉ chứa key cần thiết.
- [ ] App có cơ chế reload hoặc rollout khi config thay đổi.
- [ ] Secret files có permission phù hợp.
- [ ] Volume mount không ghi đè nhầm directory quan trọng trong image.
- [ ] Có dashboard/alert cho disk pressure và ephemeral storage nếu workload ghi nhiều.

### Tránh làm

- Dùng `emptyDir` cho database data.
- Mount `/` hoặc `/var/run/docker.sock` bằng `hostPath` cho app bình thường.
- Để mọi secret trong cùng một volume mount cho mọi container.
- Dùng ConfigMap update nhưng app không reload và không rollout.
- Không đặt resource/ephemeral storage limit cho workload ghi file tạm lớn.

## Performance Considerations

- `emptyDir` trên disk tiêu thụ ephemeral storage của node; nếu ghi quá nhiều có thể gây `DiskPressure` và eviction.
- `emptyDir.medium: Memory` dùng RAM/tmpfs, ảnh hưởng trực tiếp đến memory usage và OOM risk.
- Mount nhiều ConfigMap/Secret hoặc file lớn có thể làm Pod startup chậm hơn và tăng tải kubelet/API cache.
- `hostPath` performance phụ thuộc disk node cụ thể; Pod reschedule sang node khác có thể vừa mất data vừa đổi performance profile.
- Với workload ghi file tạm lớn, đặt `resources.requests/limits.ephemeral-storage` và theo dõi `df -h`, inode, events.

## Debugging Checklist

Khi Pod lỗi vì volume:

1. `kubectl describe pod <pod>` để đọc events.
2. Kiểm tra `volumes` và `volumeMounts` có trùng `name` không.
3. Kiểm tra ConfigMap/Secret tồn tại đúng namespace.
4. Kiểm tra mount path có ghi đè directory app cần không.
5. Với `hostPath`, kiểm tra path tồn tại trên node và type đúng.
6. Với permission issue, kiểm tra user trong container, `defaultMode`, `fsGroup`.
7. Với disk issue, kiểm tra node disk pressure và ephemeral storage usage.

## Liên hệ với kiến thức đã biết

Trong microservices, volumes thường xuất hiện ở các pattern quen thuộc: API ghi upload tạm trước khi đẩy object storage, sidecar đọc log file, init container render config, app đọc certificate/token từ file. Với Redis/PostgreSQL/Kafka, Day 22 chỉ đủ cho scratch/config; data bền vững phải chuyển sang PV/PVC và backup strategy.

## Tóm tắt

Volumes là bước đầu để hiểu storage trong Kubernetes. Chúng giải quyết nhu cầu chia sẻ file trong Pod, scratch space, config và secret injection. Nhưng chỉ một phần nhỏ trong đó là storage bền vững. Khi dữ liệu cần sống lâu hơn Pod hoặc cần binding với storage backend, bạn chuyển sang PV/PVC, StorageClass và CSI ở các ngày tiếp theo.

## Câu hỏi tự kiểm tra

1. `emptyDir` tồn tại qua container restart nhưng mất trong trường hợp nào?
2. Vì sao `subPath` cần thận trọng với ConfigMap/Secret update?
3. Khi nào `hostPath` là lựa chọn hợp lý?
4. `emptyDir.medium: Memory` ảnh hưởng đến memory/eviction như thế nào?
5. Vì sao mount volume có thể làm app mất file có sẵn trong image ở cùng path?

## Tài liệu tham khảo

- Kubernetes Documentation: Volumes, ConfigMaps, Secrets, Ephemeral Storage.
- Kubernetes Documentation: Pod Security Standards.
- K3s Documentation: Storage và local-path provisioner overview.
