"""
Static-correctness tests for docker-compose.rocm.yml.

These do NOT exercise docker — only YAML parsing and structural
expectations. Goal: catch typos, missing service overrides, and port
collisions before we burn cloud hours discovering them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_BASE = REPO_ROOT / "docker-compose.yml"
COMPOSE_ROCM = REPO_ROOT / "docker-compose.rocm.yml"


@pytest.fixture(scope="module")
def base_compose() -> dict:
    return yaml.safe_load(COMPOSE_BASE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rocm_compose() -> dict:
    return yaml.safe_load(COMPOSE_ROCM.read_text(encoding="utf-8"))


# ── Service presence ────────────────────────────────────────────────────────

class TestServicesPresent:
    def test_vllm_orchestrator_defined(self, rocm_compose):
        assert "vllm-orchestrator" in rocm_compose["services"]

    def test_vllm_agents_defined(self, rocm_compose):
        assert "vllm-agents" in rocm_compose["services"]

    def test_tribe_scorer_defined(self, rocm_compose):
        assert "tribe_scorer" in rocm_compose["services"]

    def test_mirofish_overridden(self, rocm_compose):
        assert "mirofish" in rocm_compose["services"]


# ── Port wiring ─────────────────────────────────────────────────────────────

def _host_ports(service: dict) -> list[int]:
    """Extract host-side ports from a service's ports list."""
    out = []
    for spec in service.get("ports", []) or []:
        # Accepted forms: "127.0.0.1:HOST:CONTAINER" or "HOST:CONTAINER".
        match = re.match(r"^(?:[\w\.]+:)?(\d+):\d+$", str(spec))
        if match:
            out.append(int(match.group(1)))
    return out


class TestPortWiring:
    def test_no_host_port_collision_within_overlay(self, rocm_compose):
        """No two services in the rocm overlay may bind the same host port."""
        seen: dict[int, str] = {}
        for name, svc in rocm_compose["services"].items():
            for port in _host_ports(svc):
                assert port not in seen, (
                    f"Host port {port} bound by both '{seen[port]}' and '{name}'"
                )
                seen[port] = name

    def test_no_host_port_collision_against_base(self, base_compose, rocm_compose):
        """Overlay services must not collide with base-compose host ports."""
        base_seen: dict[int, str] = {}
        for name, svc in base_compose["services"].items():
            for port in _host_ports(svc):
                base_seen[port] = name
        for name, svc in rocm_compose["services"].items():
            if name in base_compose["services"]:
                # Service is being overridden — port may legitimately match.
                continue
            for port in _host_ports(svc):
                assert port not in base_seen, (
                    f"Overlay '{name}' host port {port} collides with base "
                    f"service '{base_seen[port]}'"
                )

    def test_vllm_orchestrator_host_port_is_18000(self, rocm_compose):
        ports = _host_ports(rocm_compose["services"]["vllm-orchestrator"])
        assert 18000 in ports

    def test_vllm_agents_host_port_is_18001(self, rocm_compose):
        ports = _host_ports(rocm_compose["services"]["vllm-agents"])
        assert 18001 in ports


# ── GPU passthrough ─────────────────────────────────────────────────────────

class TestGpuPassthrough:
    @pytest.mark.parametrize(
        "service_name", ["vllm-orchestrator", "vllm-agents", "tribe_scorer"],
    )
    def test_gpu_devices_mounted(self, rocm_compose, service_name):
        svc = rocm_compose["services"][service_name]
        devices = svc.get("devices", []) or []
        device_strs = [str(d) for d in devices]
        assert any("/dev/kfd" in d for d in device_strs), (
            f"{service_name}: missing /dev/kfd passthrough (AMD kernel driver)"
        )
        assert any("/dev/dri" in d for d in device_strs), (
            f"{service_name}: missing /dev/dri passthrough (AMD render nodes)"
        )

    @pytest.mark.parametrize(
        "service_name", ["vllm-orchestrator", "vllm-agents", "tribe_scorer"],
    )
    def test_video_group_added(self, rocm_compose, service_name):
        svc = rocm_compose["services"][service_name]
        assert "video" in (svc.get("group_add") or []), (
            f"{service_name}: missing 'video' group; cannot read /dev/dri/render*"
        )


# ── Model env-var wiring ────────────────────────────────────────────────────

class TestModelEnvWiring:
    def test_orchestrator_command_references_model_var(self, rocm_compose):
        cmd = rocm_compose["services"]["vllm-orchestrator"].get("command") or []
        joined = " ".join(str(c) for c in cmd)
        assert "${VLLM_ORCHESTRATOR_MODEL" in joined, (
            "vllm-orchestrator command must reference VLLM_ORCHESTRATOR_MODEL"
        )

    def test_agents_command_references_model_var(self, rocm_compose):
        cmd = rocm_compose["services"]["vllm-agents"].get("command") or []
        joined = " ".join(str(c) for c in cmd)
        assert "${VLLM_AGENT_MODEL" in joined

    def test_orchestrator_default_is_qwen35_27b(self, rocm_compose):
        cmd = " ".join(str(c) for c in rocm_compose["services"]["vllm-orchestrator"]["command"])
        assert "Qwen/Qwen3.5-27B" in cmd, "primary orchestrator default model not set"

    def test_agents_default_is_qwen35_9b(self, rocm_compose):
        cmd = " ".join(str(c) for c in rocm_compose["services"]["vllm-agents"]["command"])
        assert "Qwen/Qwen3.5-9B" in cmd, "primary agent default model not set"


# ── MiroFish routing through vllm-agents ────────────────────────────────────

class TestMirofishRouting:
    def test_mirofish_llm_base_url_points_to_vllm_agents(self, rocm_compose):
        env = rocm_compose["services"]["mirofish"]["environment"]
        assert env["LLM_BASE_URL"].rstrip("/") == "http://vllm-agents:8001/v1"

    def test_mirofish_depends_on_vllm_agents(self, rocm_compose):
        deps = rocm_compose["services"]["mirofish"].get("depends_on", {})
        assert "vllm-agents" in deps

    def test_mirofish_does_not_depend_on_litellm_in_overlay(self, rocm_compose):
        """LiteLLM is bypassed entirely in the rocm stack."""
        deps = rocm_compose["services"]["mirofish"].get("depends_on", {})
        assert "litellm" not in deps


# ── HF cache volume sharing ─────────────────────────────────────────────────

class TestHfCacheSharing:
    def test_both_vllm_services_mount_same_cache_volume(self, rocm_compose):
        """Single download per model — saves ~80 GB and ~20 min on first start."""
        a = rocm_compose["services"]["vllm-orchestrator"].get("volumes", [])
        b = rocm_compose["services"]["vllm-agents"].get("volumes", [])
        a_volumes = [str(v).split(":")[0] for v in a]
        b_volumes = [str(v).split(":")[0] for v in b]
        assert "vllm_hf_cache" in a_volumes
        assert "vllm_hf_cache" in b_volumes

    def test_vllm_hf_cache_volume_declared(self, rocm_compose):
        assert "vllm_hf_cache" in (rocm_compose.get("volumes") or {})
