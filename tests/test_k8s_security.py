from pathlib import Path

import yaml


def test_container_source_is_readable_by_the_non_root_runtime_user() -> None:
    dockerfile = (Path(__file__).parents[1] / "deploy" / "Dockerfile").read_text()
    assert "chmod -R a+rX /app" in dockerfile
    assert "USER 10001:10001" in dockerfile


def test_network_policy_allows_only_front_doors_and_same_namespace() -> None:
    manifest = yaml.safe_load((Path(__file__).parents[1] / "deploy" / "k8s" / "networkpolicy.yaml").read_text())
    sources = manifest["spec"]["ingress"][0]["from"]
    namespaces = {
        source.get("namespaceSelector", {}).get("matchLabels", {}).get("kubernetes.io/metadata.name")
        for source in sources
    }
    pod_apps = {
        source.get("podSelector", {}).get("matchLabels", {}).get("app")
        for source in sources
    }
    assert {"ingress", "edge"} <= namespaces
    assert "nginx-proxy-manager" in pod_apps
    assert any(source == {"podSelector": {}} for source in sources)


def test_permission_init_has_only_the_chown_capability_it_needs() -> None:
    manifest = yaml.safe_load((Path(__file__).parents[1] / "deploy" / "k8s" / "deployment.yaml").read_text())
    security = manifest["spec"]["template"]["spec"]["initContainers"][0]["securityContext"]

    assert security["capabilities"]["drop"] == ["ALL"]
    assert security["capabilities"]["add"] == ["CHOWN"]
    assert security["allowPrivilegeEscalation"] is False
