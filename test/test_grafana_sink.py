"""
Tests for GrafanaSink — verifies batching, background flushing, and silent failure
for both OTLP (Grafana Cloud) and Loki (self-hosted) protocols.
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from steely.grafana import GrafanaSink
from steely.logger import Logger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_received: list = []
_received_lock = threading.Lock()


class _MockHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        with _received_lock:
            _received.append(json.loads(body))
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args):
        pass


def _start_mock_server():
    server = HTTPServer(("127.0.0.1", 0), _MockHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, port


def _wait_for_requests(count=1, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        with _received_lock:
            if len(_received) >= count:
                return True
        time.sleep(0.05)
    return False


def _entry(level="INFO", owner="TEST"):
    return dict(
        level=level,
        message="test message",
        app_name="TESTAPP",
        owner=owner,
        timestamp="08-05-2026 12:00:00",
        content="08-05-2026 12:00:00 [TESTAPP] [TEST] [INFO]: test message",
    )


def setup_function():
    _received.clear()


# ---------------------------------------------------------------------------
# Shared behaviour (protocol-agnostic)
# ---------------------------------------------------------------------------

def test_flush_interval_triggers_send():
    server, port = _start_mock_server()
    sink = GrafanaSink(url=f"http://127.0.0.1:{port}", protocol="loki",
                       batch_size=100, flush_interval=0.3)
    for _ in range(3):
        sink(**_entry())
    time.sleep(0.7)
    sink.close()
    server.shutdown()
    with _received_lock:
        assert len(_received) >= 1


def test_network_error_does_not_raise():
    sink = GrafanaSink(url="http://127.0.0.1:19999", batch_size=2, flush_interval=60.0)
    for _ in range(2):
        sink(**_entry())
    sink.flush()   # must not propagate any exception
    sink.close()


# ---------------------------------------------------------------------------
# Loki protocol tests
# ---------------------------------------------------------------------------

def test_loki_batch_size_triggers_flush():
    server, port = _start_mock_server()
    sink = GrafanaSink(url=f"http://127.0.0.1:{port}", protocol="loki",
                       batch_size=10, flush_interval=60.0)
    for _ in range(10):
        sink(**_entry())

    _wait_for_requests()
    sink.close()
    server.shutdown()

    with _received_lock:
        total = sum(len(s["values"]) for r in _received for s in r["streams"])
    assert total == 10


def test_loki_explicit_flush():
    server, port = _start_mock_server()
    sink = GrafanaSink(url=f"http://127.0.0.1:{port}", protocol="loki",
                       batch_size=100, flush_interval=60.0)
    for _ in range(5):
        sink(**_entry())
    sink.flush()
    with _received_lock:
        total = sum(len(s["values"]) for r in _received for s in r["streams"])
    assert total == 5
    sink.close()
    server.shutdown()


def test_loki_payload_structure():
    server, port = _start_mock_server()
    sink = GrafanaSink(url=f"http://127.0.0.1:{port}", protocol="loki",
                       labels={"app": "myapp", "env": "test"},
                       batch_size=1, flush_interval=60.0)

    sink(**_entry(level="ERROR", owner="MODULE"))
    _wait_for_requests()
    sink.close()
    server.shutdown()

    with _received_lock:
        payload = _received[0]

    assert "streams" in payload
    stream = payload["streams"][0]
    assert stream["stream"]["level"] == "error"
    assert stream["stream"]["owner"] == "module"
    assert stream["stream"]["app"] == "myapp"
    assert stream["stream"]["env"] == "test"
    ts_ns, line = stream["values"][0]
    assert int(ts_ns) > 0
    assert "test message" in line


def test_loki_global_integration():
    server, port = _start_mock_server()
    sink = Logger.set_global_grafana(
        url=f"http://127.0.0.1:{port}",
        labels={"app": "steely-test"},
        protocol="loki",
        batch_size=1,  # send immediately, no race with flush()
        flush_interval=60.0,
    )
    logger = Logger("integration-test")
    logger.info("from global grafana loki")
    logger.error("error via global loki")
    _wait_for_requests(2)
    with _received_lock:
        total = sum(len(s["values"]) for r in _received for s in r["streams"])
    assert total == 2
    sink.close()
    server.shutdown()
    Logger._global_grafana = None


# ---------------------------------------------------------------------------
# OTLP protocol tests
# ---------------------------------------------------------------------------

def test_otlp_batch_size_triggers_flush():
    server, port = _start_mock_server()
    sink = GrafanaSink(url=f"http://127.0.0.1:{port}", protocol="otlp",
                       batch_size=10, flush_interval=60.0)
    for _ in range(10):
        sink(**_entry())

    _wait_for_requests()
    sink.close()
    server.shutdown()

    with _received_lock:
        total = sum(
            len(sl["logRecords"])
            for r in _received
            for rl in r["resourceLogs"]
            for sl in rl["scopeLogs"]
        )
    assert total == 10


def test_otlp_explicit_flush():
    server, port = _start_mock_server()
    sink = GrafanaSink(url=f"http://127.0.0.1:{port}", protocol="otlp",
                       batch_size=100, flush_interval=60.0)
    for _ in range(5):
        sink(**_entry())
    sink.flush()
    with _received_lock:
        total = sum(
            len(sl["logRecords"])
            for r in _received
            for rl in r["resourceLogs"]
            for sl in rl["scopeLogs"]
        )
    assert total == 5
    sink.close()
    server.shutdown()


def test_otlp_payload_structure():
    server, port = _start_mock_server()
    sink = GrafanaSink(
        url=f"http://127.0.0.1:{port}",
        protocol="otlp",
        labels={"service.name": "myapp", "deployment.environment": "test"},
        batch_size=1,
        flush_interval=60.0,
    )

    sink(**_entry(level="ERROR", owner="MODULE"))
    _wait_for_requests()
    sink.close()
    server.shutdown()

    with _received_lock:
        payload = _received[0]

    assert "resourceLogs" in payload
    rl = payload["resourceLogs"][0]

    # resource.attributes should reflect the labels dict
    res_attrs = {a["key"]: a["value"]["stringValue"] for a in rl["resource"]["attributes"]}
    assert res_attrs["service.name"] == "myapp"
    assert res_attrs["deployment.environment"] == "test"

    log_record = rl["scopeLogs"][0]["logRecords"][0]
    assert log_record["severityText"] == "ERROR"
    assert log_record["severityNumber"] == 17
    assert int(log_record["timeUnixNano"]) > 0
    assert "test message" in log_record["body"]["stringValue"]

    attrs = {a["key"]: a["value"]["stringValue"] for a in log_record["attributes"]}
    assert attrs["owner"] == "MODULE"
    assert attrs["app"] == "TESTAPP"


def test_otlp_severity_mapping():
    """Verify steely levels map to correct OTLP severityText values."""
    server, port = _start_mock_server()
    cases = [
        ("INFO",     "INFO",  9),
        ("WARNING",  "WARN",  13),
        ("ERROR",    "ERROR", 17),
        ("CRITICAL", "FATAL", 21),
        ("TEST",     "DEBUG", 5),
    ]
    for level, expected_text, expected_num in cases:
        _received.clear()
        sink = GrafanaSink(url=f"http://127.0.0.1:{port}", protocol="otlp",
                           batch_size=1, flush_interval=60.0)
        sink(**_entry(level=level))
        _wait_for_requests()
        sink.close()
        with _received_lock:
            lr = _received[0]["resourceLogs"][0]["scopeLogs"][0]["logRecords"][0]
        assert lr["severityText"] == expected_text, f"level={level}"
        assert lr["severityNumber"] == expected_num, f"level={level}"

    server.shutdown()


def test_otlp_global_integration():
    server, port = _start_mock_server()
    sink = Logger.set_global_grafana(
        url=f"http://127.0.0.1:{port}",
        labels={"service.name": "steely-test"},
        batch_size=1,  # send immediately, no race with flush()
        flush_interval=60.0,
    )
    logger = Logger("integration-test")
    logger.info("from global grafana otlp")
    logger.error("error via global otlp")
    _wait_for_requests(2)
    with _received_lock:
        total = sum(
            len(sl["logRecords"])
            for r in _received
            for rl in r["resourceLogs"]
            for sl in rl["scopeLogs"]
        )
    assert total == 2
    sink.close()
    server.shutdown()
    Logger._global_grafana = None
