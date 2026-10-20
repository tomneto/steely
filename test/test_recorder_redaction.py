"""Tests for the FastAPI recorder redaction layer (steely.fastapi.recorder._redact)."""

import json
import os

from steely.fastapi.recorder._redact import (
    REDACTED,
    normalize_sensitive_headers,
    redact_body,
    redact_headers,
)
from steely.fastapi.recorder.curl import CurlRecorder
from steely.fastapi.recorder.postman import PostmanRecorder

SECRET = "Bearer super-secret-token"


class TestRedactHeaders:
    def test_masks_default_sensitive_headers(self):
        out = redact_headers(
            {
                "Authorization": SECRET,
                "Cookie": "session=abc",
                "X-API-Key": "k",
                "Accept": "application/json",
            }
        )
        assert out["Authorization"] == REDACTED
        assert out["Cookie"] == REDACTED
        assert out["X-API-Key"] == REDACTED
        assert out["Accept"] == "application/json"

    def test_matching_is_case_insensitive(self):
        assert redact_headers({"AUTHORIZATION": SECRET})["AUTHORIZATION"] == REDACTED

    def test_custom_header_set_replaces_defaults(self):
        out = redact_headers({"Authorization": SECRET, "X-Tenant": "acme"}, {"x-tenant"})
        assert out["X-Tenant"] == REDACTED
        assert out["Authorization"] == SECRET

    def test_disabled_returns_values_verbatim(self):
        out = redact_headers({"Authorization": SECRET}, enabled=False)
        assert out["Authorization"] == SECRET

    def test_input_is_not_mutated(self):
        original = {"Authorization": SECRET}
        redact_headers(original)
        assert original["Authorization"] == SECRET

    def test_normalize_none_gives_defaults(self):
        assert "authorization" in normalize_sensitive_headers(None)
        assert normalize_sensitive_headers(["X-Foo"]) == {"x-foo"}


class TestRedactBody:
    def test_masks_sensitive_keys(self):
        out = redact_body({"user": "ana", "password": "hunter2", "token": "t"})
        assert out == {"user": "ana", "password": REDACTED, "token": REDACTED}

    def test_partial_key_match(self):
        out = redact_body({"refresh_token": "r", "api_key_id": "a"})
        assert out == {"refresh_token": REDACTED, "api_key_id": REDACTED}

    def test_walks_nested_structures(self):
        out = redact_body({"items": [{"secret": "s"}, {"ok": 1}]})
        assert out == {"items": [{"secret": REDACTED}, {"ok": 1}]}

    def test_non_mapping_body_passes_through(self):
        assert redact_body("plain text") == "plain text"
        assert redact_body(None) is None

    def test_disabled_returns_body_verbatim(self):
        body = {"password": "hunter2"}
        assert redact_body(body, enabled=False) == body

    def test_input_is_not_mutated(self):
        body = {"password": "hunter2"}
        redact_body(body)
        assert body["password"] == "hunter2"

    def test_deep_recursion_is_bounded(self):
        deep = current = {}
        for _ in range(50):
            current["nested"] = {}
            current = current["nested"]
        current["password"] = "hunter2"
        redact_body(deep)  # must return, not blow the stack


class TestCurlRecorderRedaction:
    def _record(self, tmp_path, **kwargs):
        rec = CurlRecorder("demo", output_dir=str(tmp_path), **kwargs)
        rec.record_request(
            method="POST",
            url="http://api.test/login",
            headers={"Authorization": SECRET, "Content-Type": "application/json"},
            body={"user": "ana", "password": "hunter2"},
            path="/login",
        )
        with open(rec.script_path) as f:
            return f.read()

    def test_secrets_never_hit_disk_by_default(self, tmp_path):
        script = self._record(tmp_path)
        assert "super-secret-token" not in script
        assert "hunter2" not in script
        assert REDACTED in script
        assert "ana" in script  # non-sensitive fields survive

    def test_opt_in_keeps_auth_header(self, tmp_path):
        script = self._record(tmp_path, redact_headers=False)
        assert SECRET in script
        assert "hunter2" not in script  # body redaction is independent

    def test_body_redaction_can_be_disabled(self, tmp_path):
        script = self._record(tmp_path, redact_body=False)
        assert "hunter2" in script
        assert "super-secret-token" not in script

    def test_custom_sensitive_headers(self, tmp_path):
        script = self._record(tmp_path, sensitive_headers={"content-type"})
        assert SECRET in script
        assert "application/json" not in script


class TestPostmanRecorderRedaction:
    def _record(self, tmp_path, **kwargs):
        rec = PostmanRecorder("demo", output_dir=str(tmp_path), **kwargs)
        rec.record_request(
            method="POST",
            url="http://api.test/login",
            headers={"Authorization": SECRET, "Content-Type": "application/json"},
            query_params={},
            body={"user": "ana", "password": "hunter2"},
            path="/login",
        )
        with open(rec.collection_path) as f:
            return json.load(f), f

    def test_secrets_never_hit_disk_by_default(self, tmp_path):
        collection, _ = self._record(tmp_path)
        raw = json.dumps(collection)
        assert "super-secret-token" not in raw
        assert "hunter2" not in raw
        headers = {h["key"]: h["value"] for h in collection["item"][0]["request"]["header"]}
        assert headers["Authorization"] == REDACTED
        assert headers["Content-Type"] == "application/json"

    def test_opt_in_keeps_auth_header(self, tmp_path):
        collection, _ = self._record(tmp_path, redact_headers=False)
        headers = {h["key"]: h["value"] for h in collection["item"][0]["request"]["header"]}
        assert headers["Authorization"] == SECRET

    def test_collection_file_is_written(self, tmp_path):
        collection, _ = self._record(tmp_path)
        assert os.path.exists(os.path.join(str(tmp_path), "demo.json"))
        assert collection["item"][0]["name"] == "POST /login"
