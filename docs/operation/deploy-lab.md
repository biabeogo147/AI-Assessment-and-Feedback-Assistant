# Triển khai lab

Lab là một bản chạy thật cho **năm người trong team**, trên một máy EC2 ở Singapore, sau HTTPS.
Mọi thứ nằm ở `deploy/lab/`; plan là `docs/plans/active/2026-10-20-lab-deploy-aws-plan.md`.
Chạy trên máy mình thì đọc [Local Development](../local-development.md). Bản đồ của mọi thành phần
và lý do của chúng: [Kiến trúc lab](infrastructure.md).

```text
Internet ──443──► Caddy (FE tĩnh, /api) ──► be ──► Postgres · Redis · MinIO · Mongo
                                                        agent · ingest · document · index
```

| Thứ | Ở đâu |
| --- | --- |
| Máy | Một EC2 `m7i-flex.large` (8 GB, free-tier ở account này), Ubuntu 24.04, ổ 30 GB |
| Tên miền | Giáo viên `teacher.<base_domain>`, học sinh `student.<base_domain>`; `base_domain` trong `terraform.tfvars`, hai bản ghi A trỏ về Elastic IP; Caddy tự xin chứng chỉ Let's Encrypt |
| Vào máy | SSH (cổng 22 chỉ mở cho IP trong `ssh_cidrs`), hoặc SSM Session Manager |
| Bí mật | SSM Parameter Store, tiền tố `/aiafa/lab/` |
| Backup | `pg_dump` hằng đêm lên một bucket S3, giữ 7 ngày |

## Cần có ở máy mình

- `aws` CLI đã đăng nhập vào account lab, và [Session Manager plugin](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html).
- `terraform` ≥ 1.6.
- Repo trên GitHub ở chế độ **public**, và `deploy/lab/` đã có trên nhánh `main`: máy lab `git
  clone` nhánh ấy, không kèm khoá.

## Lần đầu

**1. Thêm khoá model vào SSM.** Terraform không bao giờ cầm khoá thật, nên bạn tự thêm, cùng tiền tố.
`read -s` để khoá không vào lịch sử shell:

```bash
read -rs KEY && aws ssm put-parameter --region ap-southeast-1 --type SecureString \
  --name /aiafa/lab/CLAUDE_API_KEY --value "$KEY" && unset KEY
```

| Tham số | Bắt buộc? | Dùng cho |
| --- | --- | --- |
| `CLAUDE_API_KEY` | có | Kriky (`claude-haiku-5-5`), tóm tắt mục lục, đọc banner chương |
| `JEV_API_KEY` | không | Chọn skill cho Kriky, xếp cấp tiêu đề. Thiếu thì đi đường luật |
| `OPENAI_API_KEY` | không | Chỉ khi đổi provider trong `deploy/lab/lab.env` |

Thêm khoá **sau** khi máy đã lên cũng được: trên máy lab chạy `render-env.sh` rồi `up -d` (mục
*Việc thường ngày*). Thiếu `CLAUDE_API_KEY` thì `render-env.sh` tắt model (`LLM_ENABLED=false`):
Kriky trả nội dung dựng sẵn, và mục lục tài liệu không có tóm tắt.

**2. Apply.** Mở SSH cho mạng của team bằng một `terraform.tfvars` (gitignore: repo public, IP và
email không vào git):

```hcl
ssh_cidrs      = ["<IPv4 của mạng team>/32"]   # curl -s https://checkip.amazonaws.com
ssh_public_key = "ssh-ed25519 AAAA… aiafa-lab"   # nội dung ~/.ssh/aiafa-lab.pub
alert_email    = "ban@example.com"
base_domain    = "example.com"                  # bắt buộc: teacher.example.com, student.example.com
```

```bash
cd deploy/lab/terraform
terraform init
terraform apply -target=aws_eip.lab    # chỉ xin Elastic IP
terraform output -raw public_ip
```

Tạo hai bản ghi A, `teacher` và `student`, trỏ về IP ấy ở nơi quản DNS của `base_domain`. Chờ cả hai
phân giải được rồi mới dựng phần còn lại:

```bash
nslookup teacher.example.com 8.8.8.8      # phải ra đúng IP
nslookup student.example.com 8.8.8.8
terraform apply
```

Terraform không quản bản ghi DNS: tên miền có thể dùng chung với dự án khác, và `destroy` lab không
được đụng vào zone của nó. Bản ghi phải **phân giải được trước** khi Caddy chạy, vì Let's Encrypt kiểm
tên qua HTTP-01: xin hỏng nhiều lần là chạm giới hạn tần suất của Let's Encrypt. Cũng kiểm hai tên ấy
**không** có bản ghi AAAA trỏ đi nơi khác, và CAA của zone (nếu có) cho phép `letsencrypt.org`.

Bỏ `ssh_cidrs` thì không mở cổng 22, chỉ vào bằng SSM. IP nhà mạng đổi thì sửa `ssh_cidrs` rồi
`apply` lại: chỉ security group đổi, máy giữ nguyên. Account mới có thể có VPC mặc định mà không có
subnet: Terraform tạo subnet mặc định ở một AZ có bán loại máy (`aws_default_subnet`).

`alert_email` bật cảnh báo chi phí của AWS Budgets (50 % và 100 % của `budget_usd`, mặc định 30 USD);
để trống thì không có budget. Apply tạo 24 tài nguyên (bớt một khi không có budget, bớt một nữa khi
không có `ssh_public_key`): máy, subnet, key pair, Elastic IP, security group, IAM role, bucket backup,
budget, và bốn mật khẩu ngẫu nhiên trong SSM (Postgres, MinIO, Mongo, mật khẩu chung của tài khoản
lab).

**3. Chờ bootstrap.** Máy tự cài docker, clone repo, dựng image, bật stack và seed dữ liệu lab. Lần
đầu mất **15–25 phút**, phần lớn là image `document` (torch, paddle, model OCR). Theo dõi:

```bash
$(terraform output -raw session)
sudo tail -f /var/log/cloud-init-output.log     # dòng cuối: "==> xong"
```

Hỏng giữa chừng (log ghi bước nào) thì sửa rồi chạy lại cả bootstrap: `sudo bash
/opt/aiafa/deploy/lab/bootstrap.sh`. Chạy lại an toàn, và seed chỉ chạy một lần.

**4. Kiểm từ bên ngoài.**

```bash
export LAB_URL="$(terraform output -raw teacher_url) $(terraform output -raw student_url)"
export LAB_ACCOUNT_PASSWORD=$(aws ssm get-parameter --region ap-southeast-1 \
  --name /aiafa/lab/LAB_ACCOUNT_PASSWORD --with-decryption --query Parameter.Value --output text)
bash ../smoke.sh
```

Trên Windows, `curl` của Git Bash (mingw, Schannel) trả `000` với lỗi 43 cho mọi yêu cầu HTTPS tới
lab; `curl.exe` của Windows thì không. Đặt một `curl` gọi `/c/Windows/System32/curl.exe "$@"` lên
đầu `PATH` trước khi chạy `smoke.sh`.

Xong thì giáo viên vào `teacher_url`, học sinh vào `student_url`. Trên hai tên ấy FE chọn vai theo tên
máy, không theo hash: `teacher.…` luôn là màn giáo viên, `student.…/#/teacher` tự về màn học sinh.

`smoke.sh` kiểm: trang chủ 200; đăng ký giáo viên 403; `X-Actor` không thay được đăng
nhập; giáo viên seed đăng nhập được và cookie có cờ `Secure`; HTTP chuyển sang HTTPS; các cổng 5432,
6379, 8000, 9000, 9001, 27017 đóng.

**5. Đưa cho team.** Hai URL và mật khẩu chung của tài khoản lab
(`terraform output -raw read_password` in lệnh đọc nó). Gửi qua kênh riêng, không dán vào nhóm chat chung.

## Dữ liệu lab

`python -m be.lab_seed` (gọi qua `seed.sh`) dựng: 5 giáo viên, mỗi người 6 lớp (10A1 … 12A10, tổng
30), 1000 học sinh (33–34 em/lớp), và mỗi giáo viên 9 đề đứng ở 8 chặng: nháp, đang soạn, đã duyệt,
sắp mở, thu hồi một lớp, đang làm pha 1, đang chữa (pha 2), đã xong (2 đề). Đề đã xong cũ hơn có một
câu khó hẳn, để *Bảng theo dõi* có một dòng *tỉ lệ sai cao* thật.

| Ai | Đăng nhập bằng |
| --- | --- |
| Giáo viên | SĐT `0912000101` … `0912000105`, hay email `nhung.nguyen@example.com`, `bao.tran@…`, `thu.le@…`, `duc.hoang@…`, `ha.vu@…` |
| Học sinh | Tên đăng nhập theo luật của ADR-36 (vd. `anhnm`); `seed.sh` in học sinh đầu tiên của mỗi lớp |

**Mọi tài khoản dùng chung một mật khẩu**, `LAB_ACCOUNT_PASSWORD` trong SSM. Không có lớp nào
đứng trước màn đăng nhập (bỏ basic auth 24/10/2026), nên ai biết URL, SĐT seed và mật khẩu này là vào
được mọi tài khoản; người dùng chấp nhận, bảo mật để sau (D4 của plan).

Seed không dựng tài liệu và hội thoại Kriky: chúng cần byte trong MinIO và model thật, nên thử bằng
cách tải tệp thật và chat thật.

**Dữ liệu seed cũ dần.** Mọi lịch tính quanh lúc seed. Nhanh nhất là các lượt **đang làm dở**: bài pha 1
đang làm hết giờ sau tối đa 15 phút, vòng chữa đang mở sau vài phút (5 phút mỗi câu, như đường thật),
rồi tự nộp ở lần mở kế. Sau đó: đề *đang làm* đóng sau 3 giờ, đề *sắp mở*
mở sáng hôm sau, đề *thu hồi một lớp* mở sau 3 ngày, đề *đang chữa* hết hạn chữa sau 2 ngày. Vài
ngày sau, mọi đề đều đã qua. Seed lại (`seed.sh`) dựng lại các chặng ấy, nhưng **xoá luôn mọi thứ
team đã làm trên lab**: báo trước khi chạy.

## Việc thường ngày

Mọi lệnh dưới đây chạy **trên máy lab**, sau `$(terraform output -raw session)`.

| Việc | Lệnh |
| --- | --- |
| Đưa bản mới lên | `sudo bash /opt/aiafa/deploy/lab/deploy.sh [nhánh-hay-commit]` |
| Seed lại (xoá sạch dữ liệu) | `sudo bash /opt/aiafa/deploy/lab/seed.sh` |
| Xem container | `sudo docker compose -p aiafa-lab -f /opt/aiafa/deploy/lab/docker-compose.lab.yml ps` |
| Xem log một service | `… logs -f --tail 200 be` (hay `agent`, `document`, `index`, `ingest`, `caddy`) |
| Đổi một khoá | `aws ssm put-parameter --overwrite …` ở máy mình; trên máy lab `sudo bash /opt/aiafa/deploy/lab/render-env.sh` rồi `… up -d` |
| Backup ngay | `sudo bash /opt/aiafa/deploy/lab/backup.sh` |
| Đổi tên miền | Hai bản ghi A `teacher`, `student` của tên gốc mới trỏ về `public_ip` và phân giải được; sửa `base_domain` rồi `terraform apply` ở máy mình (chỉ tham số SSM đổi); trên máy lab `render-env.sh` rồi `… up -d caddy`. **Đừng apply khi tên mới chưa phân giải được:** mỗi lần boot máy chạy lại `render-env.sh`, nên một lần khởi động lại là Caddy sang tên mới, xin chứng chỉ không được, và lab tắt |

**Không có migration** (D5): bản mới đổi model database thì BE từ chối khởi động (`docker compose
logs be` ghi rõ cột nào thiếu). Cách ra là `seed.sh` — dữ liệu lab mất, dựng lại từ đầu.

### Xem dữ liệu lab

`.\dev.ps1 lab-ui` (PowerShell, **ở máy mình**) mở Postgres, Redis, Mongo và MinIO của lab bằng bốn UI
quen thuộc của stack dev, không đăng nhập lần nào. UI chạy bằng Docker ở máy mình
(`deploy/lab/admin-ui.yml`) và đi vào lab qua một SSH tunnel; máy lab không chạy UI nào ngoài FE, kể
cả console của MinIO (`MINIO_BROWSER=off`).

| Kho | URL | UI |
| --- | --- | --- |
| Postgres | `http://127.0.0.1:18081` | pgweb |
| Redis | `http://127.0.0.1:18082` | redis-commander |
| Mongo | `http://127.0.0.1:18083` | mongo-express |
| MinIO | `http://127.0.0.1:18084` | s3manager (console của MinIO luôn bắt đăng nhập) |

Cần: Docker Desktop đang chạy, `terraform` đã apply ở máy này (lệnh đọc `public_ip`), khoá SSH ở
`~/.ssh/aiafa-lab` (đổi bằng `AIAFA_LAB_SSH_KEY`) và IP mình nằm trong `ssh_cidrs`, aws CLI đọc được
SSM (region đổi bằng `AIAFA_LAB_REGION`). Lệnh tra IP container qua SSH, mở tunnel ở `127.0.0.1:15432`,
`16379`, `19000`, `27018`, đọc mật khẩu từ SSM (giữ trong bộ nhớ, không ghi file; chỉ vào biến môi
trường trong lúc một lệnh `docker compose` chạy), bật UI rồi in bốn URL. Ctrl+C tắt UI và đóng tunnel. Cổng khác cổng của `infra-up`, nên
chạy song song với stack dev được.

**Cả bốn UI ghi được vào dữ liệu thật của lab**, cái tester đang dùng. Deploy hay khởi động lại một
container giữa chừng làm IP của nó đổi và tunnel chết: chạy lại `lab-ui`.

### Khôi phục từ backup

```bash
aws s3 ls s3://$(terraform output -raw backup_bucket)/pg/      # ở máy mình: chọn một ngày
# trên máy lab:
aws s3 cp s3://<bucket>/pg/<ngày>.sql.gz - | gunzip | \
  sudo docker compose -p aiafa-lab -f /opt/aiafa/deploy/lab/docker-compose.lab.yml \
  exec -T postgres psql -U aiafa aiafa
```

Dump có `--clean`, nên nó xoá bảng cũ trước khi nạp.

## Tiền

Free plan trừ vào credit; hết credit hay hết hạn plan thì bắt đầu tính tiền thật.

- Máy tính **theo giờ** khi chạy. Không dùng vài ngày thì `aws ec2 stop-instances`; bật lại bằng
  `start-instances`, unit systemd tự bật stack, Elastic IP giữ nguyên địa chỉ. Lúc máy tắt vẫn tính
  tiền **Elastic IP** (IPv4 public, theo giờ) và **ổ 30 GB**, chỉ rẻ hơn nhiều.
- Không có NAT Gateway, không load balancer: hai thứ tốn tiền nhất mà lab không cần.
- Khoá model tính tiền ở nhà cung cấp, ngoài AWS; giới hạn chi đặt ở console của họ.

## Gỡ lab

```bash
cd deploy/lab/terraform && terraform destroy
```

Xoá máy, ổ đĩa, Elastic IP, bucket backup (kể cả tệp), SSM do Terraform tạo. Khoá model bạn tự thêm
còn lại trong SSM: `aws ssm delete-parameter --name /aiafa/lab/CLAUDE_API_KEY` (và tương tự).

## Chạy stack lab ở máy mình

Để thử image và compose trước khi apply, song song với stack dev (project riêng, chỉ
`127.0.0.1:8088`, không đụng cổng của `docker-compose.infra.yml`):

```bash
bash deploy/lab/local-env.sh        # .env (mật khẩu ngẫu nhiên) + .env.overrides
docker compose -p aiafa-lab -f deploy/lab/docker-compose.lab.yml up -d --build
read -rs PW && printf '%s\n' "$PW" | docker compose -p aiafa-lab -f deploy/lab/docker-compose.lab.yml \
  exec -T be python -m be.lab_seed --reset
LAB_URL=http://127.0.0.1:8088 LAB_ACCOUNT_PASSWORD="$PW" bash deploy/lab/smoke.sh
```

`.env.overrides` tắt model (`LLM_ENABLED=false`) và cờ `Secure` (HTTP thuần). Dọn: `docker compose
-p aiafa-lab -f deploy/lab/docker-compose.lab.yml down -v`.

## Chẩn đoán

| Thấy | Vì sao, làm gì |
| --- | --- |
| Trình duyệt báo chứng chỉ sai vài phút đầu | Caddy chưa xin xong. Xem `logs caddy`; cổng 80 phải mở cho Let's Encrypt |
| `render-env.sh`: *Thiếu /aiafa/lab/…* | Tham số do Terraform tạo bị xoá tay. `terraform apply` tạo lại |
| Kriky trả lời bằng nội dung dựng sẵn | Chưa có `CLAUDE_API_KEY`, nên `render-env.sh` đã tắt model. Thêm khoá vào SSM, rồi `render-env.sh` và `up -d` |
| Kriky báo model hỏng ở mọi lượt | Có khoá mà khoá sai hay hết hạn mức. `logs agent` ghi lỗi của nhà cung cấp |
| Tài liệu đứng ở *đang xử lý* rồi *xử lý hỏng* | `logs document` và `logs index`; lần đọc scan đầu chậm hơn các lần sau |
| BE không lên sau `deploy.sh` | Đổi model database: `seed.sh` (mục *Việc thường ngày*) |
| `apply` báo instance type không được phép | Free plan đổi danh sách. `aws ec2 describe-instance-types --filters Name=free-tier-eligible,Values=true`, rồi `-var instance_type=…` |
