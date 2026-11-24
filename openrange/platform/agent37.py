"""Agent37: host each agent in its own persistent cloud sandbox.

    python -m openrange.platform.agent37 deploy        create 2 sandboxes: analyst + trader
    python -m openrange.platform.agent37 status        list what we created
    python -m openrange.platform.agent37 stop          delete both sandboxes

Before deploying (once):
  1. AGENT37_API_KEY in .env   (agent37.com/dashboard/cloud/api-keys)
  2. Build the image as a template:   npx agent37 templates build . --name openrange
  3. Fill in .env with the BAND / Lyzr keys: the sandboxes get the same environment.
"""

from __future__ import annotations

import json
import sys

import requests

from openrange.core.config import PROJECT_ROOT, Settings, load_settings

STATE_FILE = PROJECT_ROOT / "data" / "agent37_instances.json"
ROLES = ("analyst", "trader")


class Agent37:
    def __init__(self, settings: Settings):
        self.key = settings.secrets.agent37_api_key
        if not self.key:
            raise SystemExit("AGENT37_API_KEY is empty. Add it to .env")
        self.cfg = settings.platform.agent37

    def create_instance(self) -> str:
        r = requests.post(f"{self.cfg.api_url}/v1/instances", timeout=60,
                          headers={"Authorization": f"Bearer {self.key}"}, json={"template": self.cfg.template})
        r.raise_for_status()
        body = r.json()
        return body.get("id") or body.get("instance_id") or body["instance"]["id"]

    def exec(self, instance_id: str, command: str, background: bool = True) -> dict:
        r = requests.post(f"{self.cfg.exec_url}/v1/instances/{instance_id}/exec", timeout=60,
                          headers={"X-Agent37-Key": self.key}, json={"command": command, "background": background})
        r.raise_for_status()
        return r.json()

    def delete_instance(self, instance_id: str) -> None:
        r = requests.delete(f"{self.cfg.api_url}/v1/instances/{instance_id}", timeout=60,
                            headers={"Authorization": f"Bearer {self.key}"})
        r.raise_for_status()


def deploy(settings: Settings) -> dict[str, str]:
    """One sandbox per agent, each running the live scheduler with its role."""
    a37 = Agent37(settings)
    instances = {}
    for role in ROLES:
        instance_id = a37.create_instance()
        a37.exec(instance_id, f"cd /app && ROLE={role} python -m openrange.orchestrator.scheduler --role {role} "
                              f"> /app/{role}.log 2>&1")
        instances[role] = instance_id
        print(f"{role:>8}: sandbox {instance_id} started")
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(instances, indent=2), encoding="utf-8")
    return instances


def stop(settings: Settings) -> None:
    if not STATE_FILE.exists():
        print("Nothing deployed.")
        return
    a37 = Agent37(settings)
    for role, instance_id in json.loads(STATE_FILE.read_text(encoding="utf-8")).items():
        a37.delete_instance(instance_id)
        print(f"{role:>8}: sandbox {instance_id} deleted")
    STATE_FILE.unlink()


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    settings = load_settings()
    if action == "deploy":
        deploy(settings)
    elif action == "stop":
        stop(settings)
    else:
        print(STATE_FILE.read_text(encoding="utf-8") if STATE_FILE.exists() else "Nothing deployed.")


if __name__ == "__main__":
    main()
