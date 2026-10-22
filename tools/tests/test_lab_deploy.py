"""Cấu hình lab (plan `lab-deploy-aws`): ranh giới của máy dev vẫn đứng trên máy lab.

Đọc thẳng `deploy/lab/` -- không chạy docker. Năm điều:

- **Chỉ caddy mở cổng.** Redis, Postgres, MinIO, Mongo không mật khẩu hay BE trần ra Internet là
  đúng cái lỗ mà basic auth đứng chắn.
- **Mọi núm của lab có thật.** Khoá trong `lab.env` hay `environment:` của một service Python phải
  có ở `.env.example` -- nơi `check_env_example_has_no_orphans` đã buộc mỗi khoá có người đọc.
- **Mỗi service chỉ cầm credential của nó**, như ở máy dev: AGENT và DOCUMENT không có URL database,
  BE và INGEST không có khoá model.
- **Lab tắt những gì máy dev bật**: danh tính tự khai, đăng ký giáo viên; cookie có cờ Secure.
- **Mỗi vai một tên máy** (plan `lab-subdomains`): Terraform dựng `teacher.` / `student.` trước tên
  gốc, và FE nhận ra vai từ đúng hai tiền tố ấy.
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


def test_basic_auth_is_on_unless_turned_off():
    caddy = _compose()["services"]["caddy"]["environment"]
    assert caddy["LAB_AUTH"] == "${LAB_AUTH:-on}"
    assert "import auth-{$LAB_AUTH:on}.caddy" in (LAB / "Caddyfile").read_text(encoding="utf-8")


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
