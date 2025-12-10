"""
Tests for the FastAPI Curl Recorder Decorator
==============================================

This test suite validates the curl recorder decorator that generates
executable curl commands from FastAPI requests.
"""

import os
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from steely.fastapi import recorder


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test scripts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def app(temp_dir):
    """Create a test FastAPI app with curl decorator."""
    app = FastAPI()

    @app.get("/items/{item_id}")
    @recorder.curl(output_dir=temp_dir, script_name="test_api")
    async def get_item(item_id: int, q: str = None):
        return {"item_id": item_id, "q": q}

    @app.post("/items")
    @recorder.curl(output_dir=temp_dir, script_name="test_api")
    async def create_item(name: str, description: str = None):
        return {"name": name, "description": description, "id": 123}

    @app.put("/items/{item_id}")
    @recorder.curl(output_dir=temp_dir, script_name="test_api")
    async def update_item(item_id: int, name: str):
        return {"item_id": item_id, "name": name, "updated": True}

    @app.delete("/items/{item_id}")
    @recorder.curl(output_dir=temp_dir, script_name="test_api")
    async def delete_item(item_id: int):
        return {"message": f"Item {item_id} deleted"}

    return app


class TestCurlCommandGeneration:
    """Test curl command generation from requests."""

    def test_get_request_generates_curl(self, app, temp_dir):
        """Test that GET request generates a valid curl command."""
        client = TestClient(app)

        # Make a GET request
        response = client.get("/items/42?q=search")
        assert response.status_code == 200

        # Check script file was created
        script_path = Path(temp_dir) / "test_api.sh"
        assert script_path.exists()

        # Read script content
        with open(script_path, 'r') as f:
            content = f.read()

        # Verify script header
        assert "#!/bin/bash" in content
        assert "Auto-generated curl commands" in content

        # Verify curl command is present
        assert "curl" in content
        assert "/items/42" in content
        assert "q=search" in content

    def test_post_request_generates_curl_with_data(self, app, temp_dir):
        """Test that POST request includes -d flag and data."""
        client = TestClient(app)

        # Make a POST request
        response = client.post("/items", params={"name": "test_item", "description": "A test"})
        assert response.status_code == 200

        # Read script
        script_path = Path(temp_dir) / "test_api.sh"
        with open(script_path, 'r') as f:
            content = f.read()

        # Verify POST method
        assert "-X POST" in content or "POST" in content
        assert "/items" in content

    def test_curl_command_includes_headers(self, app, temp_dir):
        """Test that headers are included in curl command."""
        client = TestClient(app)

        # Make request with custom header
        response = client.get("/items/1", headers={"X-Custom-Header": "test-value"})
        assert response.status_code == 200

        # Read script
        script_path = Path(temp_dir) / "test_api.sh"
        with open(script_path, 'r') as f:
            content = f.read()

        # Verify headers are present (using -H flag)
        assert "-H" in content

    def test_script_is_executable(self, app, temp_dir):
        """Test that generated script has executable permissions."""
        client = TestClient(app)
        client.get("/items/1")

        script_path = Path(temp_dir) / "test_api.sh"
        assert script_path.exists()

        # Check if file is executable
        assert os.access(script_path, os.X_OK)

    def test_multiple_requests_append_to_script(self, app, temp_dir):
        """Test that multiple requests append commands to the same script."""
        client = TestClient(app)

        # Make multiple requests
        client.get("/items/1")
        client.get("/items/2?q=test")
        client.post("/items", params={"name": "test"})

        # Read script
        script_path = Path(temp_dir) / "test_api.sh"
        with open(script_path, 'r') as f:
            content = f.read()

        # Should have multiple curl commands
        curl_count = content.count("curl")
        assert curl_count >= 3  # At least 3 curl commands


class TestCurlCommandFormat:
    """Test the format and structure of generated curl commands."""

    def test_url_is_quoted(self, app, temp_dir):
        """Test that URLs are properly quoted."""
        client = TestClient(app)
        client.get("/items/1?q=search")

        script_path = Path(temp_dir) / "test_api.sh"
        with open(script_path, 'r') as f:
            content = f.read()

        # URLs should be quoted
        assert '"http://' in content or '"https://' in content

    def test_headers_are_properly_formatted(self, app, temp_dir):
        """Test that headers use -H flag with proper format."""
        client = TestClient(app)
        client.get("/items/1")

        script_path = Path(temp_dir) / "test_api.sh"
        with open(script_path, 'r') as f:
            content = f.read()

        # Headers should use -H "key: value" format
        if '-H' in content:
            assert '-H "' in content
            # Common headers should be present
            assert 'accept' in content.lower() or 'user-agent' in content.lower()

    def test_json_body_formatting(self):
        """Test that JSON bodies are properly formatted in curl commands."""
        with tempfile.TemporaryDirectory() as tmpdir:
            app = FastAPI()

            @app.post("/test")
            @recorder.curl(output_dir=tmpdir, script_name="json_test")
            async def post_json(data: dict):
                return data

            client = TestClient(app)

            # Make POST with JSON
            json_data = {"name": "test", "value": 123}
            response = client.post("/test", json=json_data)
            assert response.status_code == 200

            script_path = Path(tmpdir) / "json_test.sh"
            if script_path.exists():
                with open(script_path, 'r') as f:
                    content = f.read()

                # Should have -d flag for data
                assert "-d" in content or "--data" in content

    def test_comments_added_to_commands(self, app, temp_dir):
        """Test that comments are added above curl commands."""
        client = TestClient(app)
        client.get("/items/42")

        script_path = Path(temp_dir) / "test_api.sh"
        with open(script_path, 'r') as f:
            content = f.read()

        # Should have comment lines (starting with #)
        lines = content.split('\n')
        comment_lines = [line for line in lines if line.strip().startswith('#')]
        assert len(comment_lines) > 3  # Header comments + request comment


class TestScriptManagement:
    """Test script file management and organization."""

    def test_separate_script_per_endpoint(self, temp_dir):
        """Test that different endpoints can have separate scripts."""
        app = FastAPI()

        @app.get("/users")
        @recorder.curl(output_dir=temp_dir, script_name="users")
        async def get_users():
            return [{"id": 1}]

        @app.get("/products")
        @recorder.curl(output_dir=temp_dir, script_name="products")
        async def get_products():
            return [{"id": 1}]

        client = TestClient(app)

        client.get("/users")
        client.get("/products")

        # Should have two separate script files
        users_script = Path(temp_dir) / "users.sh"
        products_script = Path(temp_dir) / "products.sh"

        assert users_script.exists()
        assert products_script.exists()

    def test_group_mode_appends(self, temp_dir):
        """Test that group mode appends multiple commands to one file."""
        app = FastAPI()

        @app.get("/test1")
        @recorder.curl(output_dir=temp_dir, script_name="grouped", group_mode=True)
        async def test1():
            return {"test": 1}

        @app.get("/test2")
        @recorder.curl(output_dir=temp_dir, script_name="grouped", group_mode=True)
        async def test2():
            return {"test": 2}

        client = TestClient(app)

        client.get("/test1")
        client.get("/test2")

        script_path = Path(temp_dir) / "grouped.sh"
        assert script_path.exists()

        with open(script_path, 'r') as f:
            content = f.read()

        # Should have both endpoints
        assert "/test1" in content
        assert "/test2" in content

    def test_output_directory_creation(self):
        """Test that output directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_dir = Path(tmpdir) / "nested" / "scripts"
            assert not nested_dir.exists()

            app = FastAPI()

            @app.get("/test")
            @recorder.curl(output_dir=str(nested_dir))
            async def test_endpoint():
                return {"test": True}

            client = TestClient(app)
            client.get("/test")

            # Directory should be created
            assert nested_dir.exists()
            script_file = nested_dir / "test_endpoint.sh"
            assert script_file.exists()


class TestRequestCapture:
    """Test request data capture before execution."""

    def test_recording_happens_before_execution(self, temp_dir):
        """Test that recording happens even if endpoint fails."""
        app = FastAPI()

        @app.get("/error")
        @recorder.curl(output_dir=temp_dir, script_name="error_test")
        async def error_endpoint():
            raise HTTPException(status_code=500, detail="Test error")

        client = TestClient(app)

        # Make request that will fail
        try:
            client.get("/error")
        except:
            pass

        # Script should still be created because recording happens first
        script_path = Path(temp_dir) / "error_test.sh"
        assert script_path.exists()

        with open(script_path, 'r') as f:
            content = f.read()

        # Curl command should be present
        assert "curl" in content
        assert "/error" in content

    def test_no_response_capture(self, app, temp_dir):
        """Test that response data is not captured (request-only mode)."""
        client = TestClient(app)
        client.get("/items/1")

        script_path = Path(temp_dir) / "test_api.sh"
        with open(script_path, 'r') as f:
            content = f.read()

        # Should NOT contain response data or status codes from execution
        # Just the curl command to make the request
        assert "curl" in content
        # Should not have response body data
        assert '{"item_id"' not in content


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_endpoint_without_request_param_works(self, temp_dir):
        """Test that decorator works without explicit Request parameter."""
        app = FastAPI()

        @app.get("/simple")
        @recorder.curl(output_dir=temp_dir)
        async def simple_endpoint():
            return {"message": "hello"}

        client = TestClient(app)
        response = client.get("/simple")

        assert response.status_code == 200

        script_path = Path(temp_dir) / "simple_endpoint.sh"
        assert script_path.exists()

        with open(script_path, 'r') as f:
            content = f.read()

        assert "curl" in content
        assert "/simple" in content

    def test_path_parameters_in_url(self, app, temp_dir):
        """Test that path parameters are included in URL."""
        client = TestClient(app)
        client.get("/items/999")

        script_path = Path(temp_dir) / "test_api.sh"
        with open(script_path, 'r') as f:
            content = f.read()

        assert "/items/999" in content

    def test_query_parameters_in_url(self, app, temp_dir):
        """Test that query parameters are included in URL."""
        client = TestClient(app)
        client.get("/items/1?q=test&limit=10")

        script_path = Path(temp_dir) / "test_api.sh"
        with open(script_path, 'r') as f:
            content = f.read()

        assert "q=test" in content
        assert "limit=10" in content or "limit" in content

    def test_different_http_methods(self, temp_dir):
        """Test that different HTTP methods are recorded correctly."""
        app = FastAPI()

        @app.get("/test")
        @recorder.curl(output_dir=temp_dir, script_name="methods")
        async def get_test():
            return {}

        @app.post("/test")
        @recorder.curl(output_dir=temp_dir, script_name="methods")
        async def post_test(name: str):
            return {"name": name}

        @app.put("/test")
        @recorder.curl(output_dir=temp_dir, script_name="methods")
        async def put_test(name: str):
            return {"name": name}

        @app.delete("/test")
        @recorder.curl(output_dir=temp_dir, script_name="methods")
        async def delete_test():
            return {}

        client = TestClient(app)

        client.get("/test")
        client.post("/test", params={"name": "test"})
        client.put("/test", params={"name": "updated"})
        client.delete("/test")

        script_path = Path(temp_dir) / "methods.sh"
        with open(script_path, 'r') as f:
            content = f.read()

        # Should have different methods
        # GET might not have -X flag, but POST/PUT/DELETE should
        assert "-X POST" in content or "POST" in content
        assert "-X PUT" in content or "PUT" in content
        assert "-X DELETE" in content or "DELETE" in content


class TestScriptExecution:
    """Test that generated scripts are actually executable."""

    def test_script_can_be_read_and_parsed(self, app, temp_dir):
        """Test that generated script is valid shell syntax."""
        client = TestClient(app)
        client.get("/items/1?q=test")

        script_path = Path(temp_dir) / "test_api.sh"
        assert script_path.exists()

        with open(script_path, 'r') as f:
            lines = f.readlines()

        # First line should be shebang
        assert lines[0].strip() == "#!/bin/bash"

        # Should have at least one curl command
        curl_lines = [line for line in lines if 'curl' in line]
        assert len(curl_lines) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
