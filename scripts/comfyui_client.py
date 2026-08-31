"""ComfyUI HTTP client.

Thin wrapper around ComfyUI's HTTP API. Used by the n8n image-generation
workflow to:
1. POST a workflow JSON
2. Poll for completion
3. Fetch the resulting images

ComfyUI listens on http://127.0.0.1:8188 by default (started via
comfyui/start-comfyui.bat on the Windows PC).

Tests: tests/test_comfyui_client.py
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class ComfyUIError(RuntimeError):
    """Raised when ComfyUI returns an error or is unreachable."""


class ComfyUIClient:
    """HTTP client for ComfyUI's /prompt and /history endpoints."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8188",
        *,
        timeout: float = 10.0,
        poll_interval: float = 1.0,
        max_poll_seconds: float = 600.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.max_poll_seconds = max_poll_seconds

    # ---------- low-level HTTP ----------

    def _request(self, method: str, path: str, *, body: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"} if body is not None else {}
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = resp.read().decode()
                return json.loads(payload) if payload else {}
        except urllib.error.URLError as exc:
            raise ComfyUIError(f"cannot reach ComfyUI at {url}: {exc}") from exc
        except urllib.error.HTTPError as exc:
            raise ComfyUIError(f"ComfyUI returned {exc.code}: {exc.read().decode()}") from exc

    # ---------- high-level API ----------

    def health(self) -> bool:
        """Return True if ComfyUI responds to GET /system_stats."""
        try:
            self._request("GET", "/system_stats")
            return True
        except ComfyUIError:
            return False

    def queue_prompt(self, workflow: dict[str, Any]) -> str:
        """Submit a workflow to ComfyUI. Returns the prompt_id."""
        resp = self._request("POST", "/prompt", body={"prompt": workflow})
        prompt_id = resp.get("prompt_id")
        if not prompt_id:
            raise ComfyUIError(f"no prompt_id in response: {resp}")
        return str(prompt_id)

    def get_history(self, prompt_id: str) -> dict | None:
        """Return the history entry for a prompt_id, or None if still running."""
        resp = self._request("GET", f"/history/{prompt_id}")
        return resp.get(prompt_id)

    def wait_for_completion(self, prompt_id: str) -> dict:
        """Poll until the prompt finishes. Raises ComfyUIError on timeout."""
        deadline = time.monotonic() + self.max_poll_seconds
        while time.monotonic() < deadline:
            entry = self.get_history(prompt_id)
            if entry is not None:
                status = entry.get("status", {})
                if status.get("completed", False):
                    return entry
                if status.get("error"):
                    raise ComfyUIError(f"ComfyUI error: {status['error']}")
            time.sleep(self.poll_interval)
        raise ComfyUIError(
            f"ComfyUI prompt {prompt_id} did not complete within {self.max_poll_seconds}s"
        )

    def fetch_outputs(self, prompt_id: str, output_dir: Path) -> list[Path]:
        """Download all image outputs from a finished prompt into output_dir."""
        entry = self.wait_for_completion(prompt_id)
        outputs = entry.get("outputs", {})
        saved: list[Path] = []
        output_dir.mkdir(parents=True, exist_ok=True)

        for node_id, node_output in outputs.items():
            for kind in ("images", "gifs"):
                for asset in node_output.get(kind, []):
                    filename = asset["filename"]
                    subfolder = asset.get("subfolder", "")
                    file_type = asset.get("type", "output")
                    url = f"{self.base_url}/view?filename={filename}&subfolder={subfolder}&type={file_type}"
                    out_path = output_dir / filename
                    try:
                        with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                            out_path.write_bytes(resp.read())
                            saved.append(out_path)
                    except urllib.error.URLError as exc:
                        raise ComfyUIError(f"failed to fetch {url}: {exc}") from exc

        return saved

    # ---------- convenience ----------

    def generate(
        self,
        workflow: dict[str, Any],
        output_dir: Path,
    ) -> list[Path]:
        """Queue, wait, and fetch. Returns the list of output file paths."""
        prompt_id = self.queue_prompt(workflow)
        return self.fetch_outputs(prompt_id, output_dir)


# ---------- module-level singleton for n8n to import ----------

_default_client: ComfyUIClient | None = None


def get_client(base_url: str = "http://127.0.0.1:8188") -> ComfyUIClient:
    """Return a process-wide ComfyUI client."""
    global _default_client
    if _default_client is None or _default_client.base_url != base_url.rstrip("/"):
        _default_client = ComfyUIClient(base_url=base_url)
    return _default_client
