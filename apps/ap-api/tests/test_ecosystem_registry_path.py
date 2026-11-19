"""The ecosystem registry must be found in the repository layout (development) and in the container layout (installed package,
registry mounted at /app/contracts/ecosystem/v1). No container is started; layouts are simulated on disk."""
import shutil
from pathlib import Path

import yaml

from asaa_integration import ecosystem

REPO = Path(__file__).resolve().parents[3]
REGISTRY = REPO / "contracts" / "ecosystem" / "v1" / "ecosystem-registry.json"


def settings(path=None):
    return lambda: type("S", (), {"ecosystem_registry_path": path, "ecosystem_allowed_hosts": [], "environment": "development"})()


def test_repository_layout_resolves_without_configuration(monkeypatch, tmp_path):
    monkeypatch.setattr(ecosystem, "get_settings", settings())
    monkeypatch.chdir(tmp_path)  # started from an unrelated directory: resolved relative to the package source tree
    assert ecosystem.registry_path().resolve() == REGISTRY.resolve()
    assert ecosystem.load_registry()[0]["schema"] == "asaa.ecosystem-registry.v1"


def test_container_layout_resolves_from_the_working_directory(monkeypatch, tmp_path):
    app = tmp_path / "app"
    (app / "contracts" / "ecosystem" / "v1").mkdir(parents=True)
    shutil.copy(REGISTRY, app / "contracts" / "ecosystem" / "v1" / "ecosystem-registry.json")
    site_packages = tmp_path / "usr" / "lib" / "python3.12" / "site-packages" / "asaa_integration"
    site_packages.mkdir(parents=True)
    monkeypatch.setattr(ecosystem, "__file__", str(site_packages / "ecosystem.py"))  # installed package: no repository above it
    monkeypatch.setattr(ecosystem, "get_settings", settings())
    monkeypatch.chdir(app)  # the image's WORKDIR is /app
    assert ecosystem.registry_path() == app / "contracts" / "ecosystem" / "v1" / "ecosystem-registry.json"
    assert ecosystem.load_registry()[0] is not None


def test_explicit_path_wins_and_a_missing_registry_degrades_gracefully(monkeypatch, tmp_path):
    monkeypatch.setattr(ecosystem, "get_settings", settings(str(REGISTRY)))
    assert ecosystem.registry_path() == REGISTRY
    monkeypatch.setattr(ecosystem, "get_settings", settings(str(tmp_path / "nope.json")))
    assert ecosystem.load_registry() == (None, "registry file not found")


def test_deployment_files_mount_the_registry_at_the_path_the_image_expects():
    dockerfile = (REPO / "apps" / "ap-api" / "Dockerfile").read_text()
    assert "ASAA_AP_ECOSYSTEM_REGISTRY_PATH=/app/contracts/ecosystem/v1/ecosystem-registry.json" in dockerfile
    for compose_file in ("deploy/docker-compose.yml", "deploy/local-prod/docker-compose.yml"):
        compose = yaml.safe_load((REPO / compose_file).read_text())
        api = compose["services"]["api"]
        assert api["environment"]["ASAA_AP_ECOSYSTEM_REGISTRY_PATH"] == "/app/contracts/ecosystem/v1/ecosystem-registry.json", compose_file
        mounts = [v for v in api["volumes"] if v.endswith(":/app/contracts/ecosystem/v1:ro")]
        assert len(mounts) == 1, compose_file
        host_dir = (REPO / compose_file).parent / mounts[0].split(":")[0]
        assert (host_dir / "ecosystem-registry.json").resolve() == REGISTRY.resolve(), compose_file


def test_local_prod_reaches_host_siblings_through_an_allowlisted_host():
    compose = yaml.safe_load((REPO / "deploy/local-prod/docker-compose.yml").read_text())
    env = compose["services"]["api"]["environment"]
    assert env["ASAA_AP_ECOSYSTEM_ALLOWED_HOSTS"] == '["host.docker.internal"]'
    overrides = {k: v for k, v in env.items() if k.startswith("ASAA_AP_ECOSYSTEM_") and k.endswith("_URL")}
    assert overrides and all(v.startswith("http://host.docker.internal:") for v in overrides.values())
    assert env["ASAA_AP_ECOSYSTEM_INSECURE_HTTP_HOSTS"] == '["host.docker.internal"]'
    assert ecosystem.url_allowed("http://host.docker.internal:3000/x", ["host.docker.internal"], ["host.docker.internal"])
    assert not ecosystem.url_allowed("http://host.docker.internal:3000/x", ["host.docker.internal"])
    assert not ecosystem.url_allowed("http://host.docker.internal:3000/x", [])
