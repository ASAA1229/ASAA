"""Container images are pinned to exact versions (owner decision): exact patch tag plus digest for third-party images, explicit
version-derived tags for ASAA's own local images, never latest or a bare major/minor tag."""
import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[3]
DIGEST = r"@sha256:[0-9a-f]{64}"
EXPECTED = {
    "python": r"python:3\.12\.\d+-slim" + DIGEST,     # matches the Python 3.12 target used by CI
    "postgres": r"postgres:16\.\d+" + DIGEST,
    "nginx": r"nginx:1\.27\.\d+-alpine" + DIGEST,
    "node": r"node:22\.\d+\.\d+-alpine" + DIGEST,
}
LOCAL = re.compile(r"^asaa-(api|portal):(?P<tag>.+)$")


def dockerfile_images(path):
    return [m.group(1) for m in re.finditer(r"^FROM\s+(\S+)", (REPO / path).read_text(), re.M)]


def compose_images(path):
    doc = yaml.safe_load((REPO / path).read_text())
    return [svc["image"] for svc in doc["services"].values() if "image" in svc]


def third_party(image):
    return not image.startswith("asaa-")


def check_third_party(image):
    name = image.split(":")[0]
    assert name in EXPECTED, f"unexpected base image {image}"
    assert re.fullmatch(EXPECTED[name], image), f"{image} is not pinned to an exact patch tag and digest"


def test_dockerfile_base_images_are_exact():
    images = dockerfile_images("apps/ap-api/Dockerfile") + dockerfile_images("Dockerfile.portal")
    assert [i.split(":")[0] for i in images] == ["python", "node", "nginx"]
    for image in images:
        check_third_party(image)


def test_compose_and_ci_service_images_are_exact():
    images = compose_images("deploy/docker-compose.yml") + compose_images("deploy/local-prod/docker-compose.yml")
    workflow = yaml.safe_load((REPO / ".github/workflows/postgres-integration.yml").read_text())
    images += [svc["image"] for job in workflow["jobs"].values() for svc in job.get("services", {}).values()]
    for image in filter(third_party, images):
        check_third_party(image)
    assert any(i.startswith("postgres:16.") for i in images)


@pytest.mark.parametrize("compose", ["deploy/docker-compose.yml", "deploy/local-prod/docker-compose.yml"])
def test_local_asaa_images_have_explicit_non_latest_tags(compose):
    locals_ = [i for i in compose_images(compose) if not third_party(i)]
    assert locals_
    for image in locals_:
        match = LOCAL.match(image)
        assert match, image
        tag = match.group("tag")
        default = re.fullmatch(r"\$\{[A-Z_]+:-([^}]+)\}", tag)
        assert default, f"{image}: the tag must carry an explicit default, not be variable-only"
        assert default.group(1) not in {"latest", "local", "dev", ""} and re.search(r"\d", default.group(1))


def test_local_prod_default_tags_follow_the_component_versions():
    pyproject = (REPO / "apps/ap-api/pyproject.toml").read_text()
    api_version = re.search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject).group(1)
    package = __import__("json").loads((REPO / "package.json").read_text())
    text = (REPO / "deploy/local-prod/docker-compose.yml").read_text()
    assert f"asaa-api:${{API_IMAGE_TAG:-{api_version}}}" in text
    assert f"asaa-portal:${{PORTAL_IMAGE_TAG:-{package['version']}}}" in text
    up = (REPO / "deploy/local-prod/up.ps1").read_text()
    assert "$version-$sha-" in up and "pyproject.toml" in up  # built images are tagged <version>-<commit>-<timestamp>


def test_no_latest_or_floating_tags_anywhere_in_deployment_files():
    for path in ["apps/ap-api/Dockerfile", "Dockerfile.portal", "deploy/docker-compose.yml", "deploy/local-prod/docker-compose.yml",
                 ".github/workflows/postgres-integration.yml", ".github/workflows/monitoring-ci.yml"]:
        text = (REPO / path).read_text()
        assert ":latest" not in text, path
        for image in re.findall(r"(?:image:\s*|docker run [^\n]*?)(prom/prometheus:\S+)", text):
            assert re.fullmatch(r"prom/prometheus:v\d+\.\d+\.\d+", image), image
