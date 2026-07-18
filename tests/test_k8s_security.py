from pathlib import Path

import yaml


def test_permission_init_has_only_the_chown_capability_it_needs() -> None:
    manifest = yaml.safe_load((Path(__file__).parents[1] / "deploy" / "k8s" / "deployment.yaml").read_text())
    security = manifest["spec"]["template"]["spec"]["initContainers"][0]["securityContext"]

    assert security["capabilities"]["drop"] == ["ALL"]
    assert security["capabilities"]["add"] == ["CHOWN"]
    assert security["allowPrivilegeEscalation"] is False
