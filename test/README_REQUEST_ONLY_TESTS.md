# FastAPI Postman Recorder - Request-Only Mode Tests

This test suite validates the modified `@postman` decorator that focuses on **request-only capture** for better performance. The recorder no longer captures response data, which eliminates the overhead of response interpretation.

## Test File

`test_fastapi_recorder_request_only.py` - Comprehensive test suite with **17 passing tests**

## Key Behavioral Changes Tested

### 1. Request-Only Capture
- **No response data** is captured (status codes, headers, or bodies)
- Only request information is stored: method, URL, headers, query params, body, path
- Response array in collection items is always empty: `"response": []`

### 2. Pre-Execution Recording
- Recording happens **BEFORE** the endpoint function executes
- Requests are captured even if the endpoint raises an exception
- This ensures all API calls are documented regardless of success/failure

### 3. Performance Optimization
- No overhead from response body capture
- No response status code interpretation
- Faster recording with reduced I/O operations

## Test Coverage

### TestRequestOnlyCapture (4 tests)
Tests that verify only request data is captured:
- ✅ `test_get_request_captured` - GET request with query parameters
- ✅ `test_post_request_with_body_captured` - POST request body capture
- ✅ `test_no_response_status_captured` - Verifies NO response status
- ✅ `test_recording_happens_before_execution` - Records even on errors

### TestCollectionStructure (4 tests)
Tests the Postman Collection v2.1 format structure:
- ✅ `test_collection_metadata` - Verifies collection info and schema
- ✅ `test_request_headers_captured` - Headers captured (excluding host, content-length)
- ✅ `test_url_structure` - URL format with protocol, host, path, query
- ✅ `test_json_body_formatting` - JSON body formatting in collections

### TestMultipleRequests (3 tests)
Tests behavior with multiple API calls:
- ✅ `test_same_endpoint_updates_collection` - Multiple calls update collection
- ✅ `test_different_http_methods_create_separate_entries` - Each HTTP method recorded
- ✅ `test_collection_file_updates_incrementally` - File updates after each request

### TestPerformanceOptimizations (2 tests)
Tests that confirm performance improvements:
- ✅ `test_no_response_body_capture_overhead` - No response body stored
- ✅ `test_recording_does_not_affect_response` - Actual responses unaffected

### TestEdgeCases (4 tests)
Tests edge cases and special scenarios:
- ✅ `test_endpoint_without_request_param_works` - Works without explicit Request param
- ✅ `test_endpoint_with_path_parameters` - Path parameters captured correctly
- ✅ `test_empty_query_params` - Endpoints without query params
- ✅ `test_output_directory_creation` - Creates nested directories automatically

## Running the Tests

```bash
# Run all request-only tests
python -m pytest test/test_fastapi_recorder_request_only.py -v

# Run specific test class
python -m pytest test/test_fastapi_recorder_request_only.py::TestRequestOnlyCapture -v

# Run specific test
python -m pytest test/test_fastapi_recorder_request_only.py::TestRequestOnlyCapture::test_get_request_captured -v

# Run with detailed output
python -m pytest test/test_fastapi_recorder_request_only.py -v --tb=short

# Run and show print statements
python -m pytest test/test_fastapi_recorder_request_only.py -v -s
```

## Example Collection Output

With the request-only mode, collections now look like this:

```json
{
  "info": {
    "name": "test_api",
    "description": "Auto-generated collection for test_api",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "GET /items/42",
      "request": {
        "method": "GET",
        "header": [
          {"key": "accept", "value": "*/*", "type": "text"}
        ],
        "url": {
          "raw": "http://localhost:8000/items/42?q=search",
          "protocol": "http",
          "host": ["localhost:8000"],
          "path": ["items", "42"],
          "query": [
            {"key": "q", "value": "search"}
          ]
        }
      },
      "response": []
    }
  ]
}
```

**Note**: The `response` array is now always empty for performance.

## What Changed from Original

### Before (Original Decorator)
- ❌ Captured response status codes
- ❌ Captured response headers
- ❌ Captured response bodies
- ❌ Recording happened AFTER function execution
- ❌ Response examples stored in collection

### After (Request-Only Mode)
- ✅ Only captures request data
- ✅ Recording happens BEFORE function execution
- ✅ No response interpretation overhead
- ✅ Faster performance
- ✅ Still creates valid Postman Collections

## Benefits

1. **Performance**: No overhead from response capture and serialization
2. **Reliability**: Requests captured even if endpoint crashes
3. **Simplicity**: Cleaner code focusing on request documentation
4. **Compatibility**: Still generates valid Postman Collection v2.1 format

## Integration with Existing Code

These tests are designed to work alongside the original tests in `test_fastapi_recorder.py`. They validate the new request-only behavior while maintaining backward compatibility with the Postman Collection format.

## Dependencies

- `pytest` - Test framework
- `fastapi` - Web framework
- `httpx` - Required by FastAPI TestClient
- `steely.fastapi.postman` - The decorator being tested

## Notes

- All tests use temporary directories for collection storage
- Tests are isolated and don't interfere with each other
- The `pprint` output shows the collection structure during recording
- Collections are saved to `.postman_collections/` by default (can be customized)
