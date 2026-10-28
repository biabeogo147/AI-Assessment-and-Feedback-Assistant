"""Cấu hình lab (plan `lab-deploy-aws`): ranh giới của máy dev vẫn đứng trên máy lab.

Đọc thẳng `deploy/lab/` -- không chạy docker. Sáu điều:

- **Chỉ caddy mở cổng.** Redis, Postgres, MinIO, Mongo hay BE trần ra Internet thì không còn gì
  đứng giữa chúng và người ngoài.
- **Mọi núm của lab có thật.** Khoá trong `lab.env` hay `environment:` của một service Python phải
  có ở `.env.example` -- nơi `check_env_example_has_no_orphans` đã buộc mỗi khoá có người đọc.
- **Mỗi service chỉ cầm credential của nó**, như ở máy dev: AGENT và DOCUMENT không có URL database,
  BE và INGEST không có khoá model.
- **Lab tắt những gì máy dev bật**: danh tính tự khai, đăng ký giáo viên; cookie có cờ Secure.
- **Mỗi vai một tên máy** (plan `lab-subdomains`): Terraform dựng `teacher.` / `student.` trước tên
  gốc, và FE nhận ra vai từ đúng hai tiền tố ấy.
- **Lab không chạy UI quản trị nào** (plan `lab-admin-ui`): UI xem dữ liệu chạy ở máy mình, chỉ trên
  127.0.0.1.
"""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / "deploy" / "lab"
PYTHON_SERVICES = ("be", "ingest", "agent", "document", "index")


def _env_file(path: Path) -> dict[str, str]:
    pairs = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            key, _, value = line.partition("=")
            pairs[key] = value
    return pairs


def _compose() -> dict:
    return yaml.safe_load((LAB / "docker-compose.lab.yml").read_text(encoding="utf-8"))


def _env_of(service: str) -> dict[str, str]:
    """Mọi biến một service Python nhận: `lab.env` cộng `environment:` của chính nó."""
    spec = _compose()["services"][service]
    return _env_file(LAB / "lab.env") | {
        key: str(value) for key, value in spec["environment"].items()
    }


def test_only_caddy_publishes_a_port():
    services = _compose()["services"]
    assert [name for name, spec in services.items() if spec.get("ports")] == ["caddy"]


def test_every_lab_knob_is_declared_in_env_example():
    declared = set(_env_file(ROOT / ".env.example"))
    assert set(_env_file(LAB / "lab.env")) <= declared
    for service in PYTHON_SERVICES:
        assert set(_env_of(service)) <= declared, service


def test_lab_env_holds_no_secret():
    for key in _env_file(LAB / "lab.env"):
        assert not any(word in key for word in ("PASSWORD", "SECRET", "API_KEY")), key
        assert key not in ("DATABASE_URL", "MONGO_URL"), key


@pytest.mark.parametrize("service", ["agent", "document", "index"])
def test_reporters_hold_no_database_url(service):
    assert "DATABASE_URL" not in _env_of(service)
    if service == "agent":
        assert "MONGO_URL" not in _env_of(service)


@pytest.mark.parametrize("service", ["be", "ingest"])
def test_be_side_holds_no_model_key(service):
    assert not [key for key in _env_of(service) if key.endswith("_API_KEY")]


def test_lab_turns_off_what_dev_turns_on():
    lab = _env_file(LAB / "lab.env")
    assert lab["DEV_IDENTITY_ENABLED"] == "false"
    assert lab["TEACHER_SIGN_UP_ENABLED"] == "false"
    assert lab["SESSION_COOKIE_SECURE"] == "true"


def test_scripts_run_on_linux():
    """Một CRLF trong script bash là `$'\\r': command not found` trên máy lab, không ở máy dev."""
    scripts = [*LAB.glob("*.sh"), LAB / "terraform" / "user_data.sh.tftpl"]
    assert scripts
    for script in scripts:
        assert b"\r\n" not in script.read_bytes(), script.name


def test_images_never_carry_secrets_or_books():
    """`.env` (khoá thật) và `data/` (sách scan) không bao giờ vào ngữ cảnh build của image.

    Cả hai `.dockerignore` mở đầu bằng `*` rồi chỉ mở lại vài thư mục; dòng mở lại nào chạm
    `.env` hay `data` là lọt."""
    for ignore in LAB.glob("*.dockerignore"):
        lines = [line.strip() for line in ignore.read_text(encoding="utf-8").splitlines()]
        rules = [line for line in lines if line and not line.startswith("#")]
        assert rules[0] == "*", ignore.name
        reopened = [line for line in rules if line.startswith("!")]
        assert not [line for line in reopened if ".env" in line or "data" in line], ignore.name


def test_render_env_writes_every_secret_compose_requires():
    """Mọi `${X:?…}` của compose -- thiếu là compose dừng -- đều do `render-env.sh` ghi ra."""
    compose = (LAB / "docker-compose.lab.yml").read_text(encoding="utf-8")
    required = set(re.findall(r"\$\{([A-Z_]+):\?", compose))
    written = set(
        re.findall(
            r'echo "([A-Z_]+)=\$\(quote', (LAB / "render-env.sh").read_text(encoding="utf-8")
        )
    )
    assert required and required <= written
    # Ngược lại: bí mật nào compose dùng mà không bắt buộc thì phải có mặc định, không để trống im.
    used = set(re.findall(r"\$\{([A-Z_]+)", compose))
    defaulted = set(re.findall(r"\$\{([A-Z_]+):-", compose))
    assert used <= required | defaulted


def test_terraform_and_fe_agree_on_the_two_host_prefixes():
    """Đổi một tiền tố ở Terraform mà quên FE thì trên lab, cả hai tên đều chọn vai theo hash."""
    terraform = (LAB / "terraform" / "main.tf").read_text(encoding="utf-8")
    hosts = dict(re.findall(r'(\w+)_host\s*=\s*"(\w+)\.\$\{var\.base_domain\}"', terraform))
    assert hosts == {"teacher": "teacher", "student": "student"}
    ssm = (LAB / "terraform" / "ssm.tf").read_text(encoding="utf-8")
    assert '"${local.teacher_host}, ${local.student_host}"' in ssm
    app = (ROOT / "services" / "fe" / "src" / "App.tsx").read_text(encoding="utf-8")
    for surface, prefix in hosts.items():
        # Tiền tố nào ứng với vai nào, không chỉ "có mặt": đảo hai nhánh ở FE cũng phải đỏ.
        assert re.search(
            rf'startsWith\("{prefix}\."\)\) \{{\s*return \{{ surface: "{surface}"', app
        ), surface


def test_lab_runs_no_admin_ui():
    r"""Lab chỉ chạy FE (plan `lab-admin-ui`): console có sẵn của MinIO tắt, UI xem dữ liệu chạy ở
    máy mình qua `.\dev.ps1 lab-ui`."""
    assert _compose()["services"]["minio"]["environment"]["MINIO_BROWSER"] == "off"


def test_local_admin_uis_bind_only_loopback():
    """Bốn UI của `lab-ui` không hỏi mật khẩu mà ghi được vào dữ liệu thật của lab: một cổng mở ra
    LAN là ai cùng mạng cũng sửa được lab."""
    services = yaml.safe_load((LAB / "admin-ui.yml").read_text(encoding="utf-8"))["services"]
    assert set(services) == {"pgweb", "redis-commander", "mongo-express", "s3manager"}
    for name, spec in services.items():
        assert spec["ports"] and all(p.startswith("127.0.0.1:") for p in spec["ports"]), name


def test_deploy_takes_only_a_lab_tag():
    """`deploy.sh` nhận đúng dạng tên mà `release.py` đặt (plan `lab-version`), và lấy tag ấy chứ
    không lấy một nhánh trùng tên."""
    from release import TAG

    script = (LAB / "deploy.sh").read_text(encoding="utf-8")
    pattern = re.search(r'\[\[ ! "\$ref" =~ (\S+) \]\]', script).group(1)
    for ref in (
        "lab-2026.0.1",
        "lab-2027.12.40",
        "main",
        "abc1234",
        "lab-2026.0",
        "lab-26.0.1",
        "lab-2026.00.1",
    ):
        assert bool(re.fullmatch(pattern, ref)) == bool(TAG.match(ref)), ref
    assert 'fetch --depth 1 origin "refs/tags/$ref"' in script
    assert "AIAFA_REF" not in script.split("source ", 1)[1]


def test_fe_and_be_get_the_version_deploy_sh_names():
    """Caddy dựng FE với tên bản làm build arg; BE đọc `.env.version` mà `deploy.sh` ghi -- env
    file chứ không `${…}`, nên tên còn sau một lần boot."""
    compose = _compose()
    assert compose["services"]["caddy"]["build"]["args"]["AIAFA_VERSION"].startswith(
        "${AIAFA_VERSION:-"
    )
    be_files = [entry["path"] for entry in compose["services"]["be"]["env_file"]]
    app_files = [entry["path"] for entry in compose["x-app"]["env_file"]]
    assert be_files == [*app_files, ".env.version"]  # be giữ đủ env file của mọi app
    script = (LAB / "deploy.sh").read_text(encoding="utf-8")
    assert '>"$LAB_DIR/.env.version"' in script
    assert "export AIAFA_VERSION=$ref" in script
    dockerfile = (LAB / "caddy.Dockerfile").read_text(encoding="utf-8")
    assert dockerfile.index("ARG AIAFA_VERSION") < dockerfile.index("RUN pnpm --filter fe build")
    assert dockerfile.index("RUN pnpm install") < dockerfile.index("ARG AIAFA_VERSION")
