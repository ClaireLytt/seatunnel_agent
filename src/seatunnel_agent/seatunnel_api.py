"""SeaTunnel Engine REST API client (Zeta engine v2.3+)."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

_log = logging.getLogger(__name__)


@dataclass
class SeaTunnelAPIConfig:
    base_url: str = "http://localhost:5801"
    timeout_s: int = 30


class SeaTunnelAPI:
    """HTTP client for the SeaTunnel Zeta engine REST API."""

    def __init__(self, config: SeaTunnelAPIConfig):
        self.config = config

    def _request(self, method: str, path: str, body: dict | None = None) -> Any:
        url = f"{self.config.base_url.rstrip('/')}{path}"
        data = json.dumps(body).encode() if body else None
        headers = {"Content-Type": "application/json"} if data else {}
        req = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=self.config.timeout_s) as resp:
                raw = resp.read().decode()
                return json.loads(raw) if raw.strip() else {}
        except HTTPError as exc:
            raw = exc.read().decode() if exc.fp else ""
            raise RuntimeError(
                f"SeaTunnel API {method} {path} -> {exc.code}: {raw}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(
                f"SeaTunnel API unreachable at {url}: {exc.reason}"
            ) from exc

    def submit_job(self, config_content: str, job_name: str = "") -> dict:
        params = "?jobName=" + job_name if job_name else ""
        return self._request(
            "POST",
            f"/hazelcast/rest/maps/submit-job{params}",
            json.loads(config_content)
            if isinstance(config_content, str)
            else config_content,
        )

    def get_job_info(self, job_id: str) -> dict:
        return self._request("GET", f"/hazelcast/rest/maps/job-info/{job_id}")

    def list_jobs(self) -> list[dict]:
        result = self._request("GET", "/hazelcast/rest/maps/running-jobs")
        return result if isinstance(result, list) else []

    def list_all_jobs(self) -> list[dict]:
        result = self._request("GET", "/hazelcast/rest/maps/overview")
        return result if isinstance(result, list) else []

    def cancel_job(self, job_id: str) -> dict:
        return self._request(
            "POST", f"/hazelcast/rest/maps/cancel-job/{job_id}"
        )

    def get_system_info(self) -> dict:
        return self._request(
            "GET", "/hazelcast/rest/maps/system-monitoring-information"
        )

    def test_connectivity(self) -> tuple[bool, str]:
        try:
            info = self.get_system_info()
            return True, "SeaTunnel engine connected"
        except Exception as exc:
            return False, str(exc)
