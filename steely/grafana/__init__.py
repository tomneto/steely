"""
GrafanaSink - Grafana Integration for Steely Logger
====================================================

Sends logs to Grafana in background batches via OTLP (Grafana Cloud) or
Loki push API (self-hosted), with zero impact on application performance.

Usage
-----
Grafana Cloud (OTLP — default):

>>> from steely import Logger
>>>
>>> sink = Logger.set_global_grafana(
...     url="https://otlp-gateway-prod-sa-east-1.grafana.net",
...     labels={"service.name": "my-api", "deployment.environment": "production"},
...     auth=("1628732", "glc_eyJ..."),
... )
>>> logger = Logger("my-module", "MyApp")
>>> logger.info("Hello Grafana")  # queued → batched → OTLP → Grafana Cloud

Self-hosted Loki:

>>> sink = Logger.set_global_grafana(
...     url="http://loki:3100",
...     labels={"app": "my-api"},
...     protocol="loki",
... )

Shutdown:

>>> sink.flush()
>>> sink.close()
"""

import atexit
import base64
import json
import queue
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import Literal, Optional, Tuple

__all__ = ["GrafanaSink"]

_SENTINEL = object()  # signals the worker thread to stop

_SEVERITY = {
    "INFO":        ("INFO",  9),
    "START":       ("INFO",  9),
    "SUCCESS":     ("INFO",  9),
    "OK":          ("INFO",  9),
    "WARNING":     ("WARN",  13),
    "ALERT":       ("WARN",  13),
    "ERROR":       ("ERROR", 17),
    "FAULT":       ("ERROR", 17),
    "FAIL":        ("ERROR", 17),
    "CRITICAL":    ("FATAL", 21),
    "FATAL":       ("FATAL", 21),
    "TEST":        ("DEBUG", 5),
    "TEST-RESULT": ("DEBUG", 5),
}


class GrafanaSink:
    """
    Non-blocking Grafana sink for the Steely Logger.

    Buffers log entries in a queue and flushes them to Grafana in background
    batches. Network errors are silently ignored so they never affect the
    calling application.

    Supports two protocols:
    - ``"otlp"`` (default): OTLP HTTP, used by Grafana Cloud
      (``https://otlp-gateway-prod-<region>.grafana.net``)
    - ``"loki"``: Loki push API, used by self-hosted Loki
      (``http://loki:3100``)

    Parameters
    ----------
    url : str
        Base URL of the target.
        Grafana Cloud (OTLP): ``"https://otlp-gateway-prod-sa-east-1.grafana.net"``
        Self-hosted Loki:     ``"http://loki:3100"``
    labels : dict, optional
        Static metadata for every batch.
        OTLP: becomes ``resource.attributes`` (e.g. ``{"service.name": "my-api"}``).
        Loki: becomes stream labels (keep cardinality low).
    batch_size : int, optional
        Maximum log records per HTTP request. Default 50.
    flush_interval : float, optional
        Maximum seconds between flushes. Default 5.0.
    timeout : int, optional
        HTTP request timeout in seconds. Default 3.
    auth : tuple, optional
        ``(username, password)`` for HTTP Basic Auth.
        Grafana Cloud: ``(instance_id, api_key)``.
    token : str, optional
        Bearer token (alternative to ``auth``).
    protocol : str, optional
        ``"otlp"`` (default) or ``"loki"``.
    """

    def __init__(
        self,
        url: str,
        labels: Optional[dict] = None,
        batch_size: int = 50,
        flush_interval: float = 5.0,
        timeout: int = 3,
        auth: Optional[Tuple[str, str]] = None,
        token: Optional[str] = None,
        protocol: Literal["otlp", "loki"] = "otlp",
        debug: bool = False,
        max_queue_size: int = 10_000,
    ):
        self._debug = debug
        self._protocol = protocol
        if protocol == "loki":
            self._push_url = url.rstrip("/") + "/loki/api/v1/push"
        else:
            self._push_url = url.rstrip("/") + "/otlp/v1/logs"

        self._labels = labels or {}
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._timeout = timeout

        self._auth_header: Optional[str] = None
        if auth is not None:
            credentials = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
            self._auth_header = f"Basic {credentials}"
        elif token is not None:
            self._auth_header = f"Bearer {token}"

        self._queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._worker, daemon=True, name="steely-grafana")
        self._thread.start()
        atexit.register(self.close)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def __call__(self, level: str, message: str, app_name: Optional[str], owner: str, timestamp: str, content: str, **kwargs):
        """Enqueue a log entry. Called by Logger.log() — never blocks."""
        # Build a clean log line without ANSI color codes
        parts = [timestamp]
        if app_name:
            parts.append(f"[{app_name}]")
        parts.append(f"[{owner}]")
        parts.append(f"[{level}]")
        line = " ".join(parts) + f": {message}"

        entry = {
            "ts_ns": str(time.time_ns()),
            "line": line,
            "level": level,
            "owner": owner,
            "app": app_name or "",
        }
        try:
            self._queue.put_nowait(entry)
        except queue.Full:
            pass

    def flush(self):
        """Drain the queue and send all pending entries synchronously."""
        buffer = []
        while True:
            try:
                e = self._queue.get_nowait()
                if e is not _SENTINEL:
                    buffer.append(e)
            except queue.Empty:
                break
        if buffer:
            self._send(buffer)

    def close(self):
        """Stop the background worker and flush remaining entries."""
        if self._stop.is_set():
            return
        self._stop.set()
        self._queue.put_nowait(_SENTINEL)  # wake up blocked queue.get() immediately
        self._thread.join(timeout=5)
        self.flush()  # catch anything added to queue after thread drained it

    # ------------------------------------------------------------------
    # Background worker
    # ------------------------------------------------------------------

    def _worker(self):
        buffer = []
        while True:
            try:
                entry = self._queue.get(timeout=self._flush_interval)
                if entry is _SENTINEL:
                    break
                buffer.append(entry)
                if len(buffer) >= self._batch_size:
                    self._send(buffer)
                    buffer = []
            except queue.Empty:
                if buffer:
                    self._send(buffer)
                    buffer = []
                if self._stop.is_set():
                    break

        # Send whatever is still in the local buffer
        if buffer:
            self._send(buffer)

        # Drain any items that arrived in the queue after the sentinel
        extra = []
        while True:
            try:
                e = self._queue.get_nowait()
                if e is not _SENTINEL:
                    extra.append(e)
            except queue.Empty:
                break
        if extra:
            self._send(extra)

    # ------------------------------------------------------------------
    # Send dispatch
    # ------------------------------------------------------------------

    def _send(self, entries: list):
        if self._protocol == "loki":
            self._send_loki(entries)
        else:
            self._send_otlp(entries)

    def _send_loki(self, entries: list):
        """Build Loki streams payload and POST."""
        streams: dict = {}
        for entry in entries:
            stream_labels = {**self._labels}
            stream_labels["level"] = entry["level"].lower()
            stream_labels["owner"] = entry["owner"].lower()
            if entry["app"] and "app" not in self._labels:
                stream_labels["app"] = entry["app"].lower()

            key = json.dumps(stream_labels, sort_keys=True)
            if key not in streams:
                streams[key] = {"stream": stream_labels, "values": []}
            streams[key]["values"].append([entry["ts_ns"], entry["line"]])

        payload = json.dumps({"streams": list(streams.values())}).encode("utf-8")
        self._http_post(payload)

    def _send_otlp(self, entries: list):
        """Build OTLP resourceLogs payload and POST."""
        resource_attrs = [
            {"key": k, "value": {"stringValue": str(v)}}
            for k, v in self._labels.items()
        ]

        log_records = []
        for entry in entries:
            sev_text, sev_num = _SEVERITY.get(entry["level"], ("INFO", 9))
            attrs = [{"key": "owner", "value": {"stringValue": entry["owner"]}}]
            if entry["app"]:
                attrs.append({"key": "app", "value": {"stringValue": entry["app"]}})

            log_records.append({
                "timeUnixNano": entry["ts_ns"],
                "severityText": sev_text,
                "severityNumber": sev_num,
                "body": {"stringValue": entry["line"]},
                "attributes": attrs,
            })

        payload = json.dumps({
            "resourceLogs": [{
                "resource": {"attributes": resource_attrs},
                "scopeLogs": [{"logRecords": log_records}],
            }]
        }).encode("utf-8")
        self._http_post(payload)

    def _http_post(self, payload: bytes):
        """POST payload to the configured endpoint. Network errors are silent."""
        req = urllib.request.Request(
            self._push_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        if self._auth_header:
            req.add_header("Authorization", self._auth_header)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                if self._debug:
                    print(f"[GrafanaSink] {resp.status} OK → {self._push_url}", file=sys.stderr, flush=True)
        except urllib.error.HTTPError as e:
            if self._debug:
                body = e.read().decode(errors="replace")
                print(f"[GrafanaSink] HTTP {e.code} → {self._push_url}\n  {body}", file=sys.stderr, flush=True)
        except Exception as e:
            if self._debug:
                print(f"[GrafanaSink] Error → {self._push_url}\n  {e}", file=sys.stderr, flush=True)
