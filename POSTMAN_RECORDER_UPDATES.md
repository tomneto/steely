# Postman Recorder - Request-Only Mode Updates

## Summary

The FastAPI Postman recorder decorator has been modified to operate in **request-only mode** for improved performance. This document summarizes the changes and new test coverage.

## What Changed

### Key Modifications

1. **Request-Only Capture** ✅
   - Removed all response data capture (status codes, headers, bodies)
   - Only captures request information: method, URL, headers, query params, body, path
   - Response array in collections is now always empty: `"response": []`

2. **Pre-Execution Recording** ✅
   - Recording now happens **BEFORE** endpoint execution
   - Ensures requests are captured even if endpoint crashes or raises exceptions
   - More reliable API documentation

3. **Performance Improvements** ✅
   - No overhead from response body serialization
   - No response status code interpretation
   - Faster recording with reduced I/O operations
   - Uses `pprint` for debug output instead of complex logging

4. **Code Cleanup** ✅
   - Removed unused `Response` import
   - Simplified `record_request()` method signature
   - Removed response-related parameters and logic

### Modified Files

#### `/steely/fastapi/recorder.py`
- Default output directory changed: `"./postman_collections"` → `"./.postman_collections"`
- Added `pprint` integration for debug output
- Removed response parameters from `record_request()`
- Recording moved before function execution
- Simplified wrapper logic

## Test Coverage

### New Test Suite: `test_fastapi_recorder_request_only.py`

**17 comprehensive tests** covering:

#### TestRequestOnlyCapture (4 tests)
- ✅ GET request capture with query parameters
- ✅ POST request body capture
- ✅ Verification that NO response status is captured
- ✅ Recording happens even on endpoint errors

#### TestCollectionStructure (4 tests)
- ✅ Collection metadata validation
- ✅ Request headers captured (excluding host, content-length)
- ✅ URL structure with protocol, host, path, query
- ✅ JSON body formatting

#### TestMultipleRequests (3 tests)
- ✅ Collection updates with multiple calls
- ✅ Different HTTP methods create separate entries
- ✅ Incremental file updates

#### TestPerformanceOptimizations (2 tests)
- ✅ No response body capture overhead
- ✅ Recording doesn't affect actual responses

#### TestEdgeCases (4 tests)
- ✅ Works without explicit Request parameter
- ✅ Path parameters captured correctly
- ✅ Empty query parameters handled
- ✅ Automatic directory creation

### Updated Original Tests: `test_fastapi_recorder.py`

**4 tests updated** to work with request-only mode:
- ✅ `test_postman_decorator_get_request` - Now verifies empty response array
- ✅ `test_postman_decorator_post_request` - Now verifies empty response array
- ✅ `test_postman_collection_update` - Updated expectations for request-only mode
- ✅ `test_postman_decorator_without_request_param` - Verifies request-only behavior

### Test Results

```bash
$ python -m pytest test/test_fastapi_recorder*.py -v

======================== 21 passed in 0.43s =========================
```

**100% pass rate** ✅

## Example Collection Format

### Before (Original)
```json
{
  "item": [{
    "name": "GET /users/42",
    "request": { ... },
    "response": [
      {
        "name": "Example Response (200)",
        "status": "OK",
        "code": 200,
        "header": [...],
        "body": "..."
      }
    ]
  }]
}
```

### After (Request-Only)
```json
{
  "item": [{
    "name": "GET /users/42",
    "request": {
      "method": "GET",
      "header": [...],
      "url": {
        "raw": "http://localhost:8000/users/42?q=search",
        "protocol": "http",
        "host": ["localhost:8000"],
        "path": ["users", "42"],
        "query": [{"key": "q", "value": "search"}]
      }
    },
    "response": []
  }]
}
```

## Performance Benefits

1. **Reduced I/O**: No response body serialization
2. **Faster Execution**: No post-processing of responses
3. **Lower Memory**: No response data buffering
4. **More Reliable**: Captures requests even on endpoint failures

## Usage (Unchanged)

```python
from fastapi import FastAPI
from steely.fastapi import recorder

app = FastAPI()

@app.get("/users/{user_id}")
@recorder.postman()
async def get_user(user_id: int):
    return {"user_id": user_id, "name": "John"}
```

Collections saved to `./.postman_collections/<function_name>.json`

## Compatibility

- ✅ Still generates valid Postman Collection v2.1 format
- ✅ Collections can be imported directly into Postman
- ✅ Works with both sync and async endpoints
- ✅ Automatic Request object injection
- ✅ FastAPI signature preservation maintained

## Documentation

- `test/README_REQUEST_ONLY_TESTS.md` - Detailed test documentation
- `steely/fastapi/README.md` - Usage guide (to be updated)
- `examples/fastapi_postman_example.py` - Working example

## Running Tests

```bash
# Run all postman recorder tests
python -m pytest test/test_fastapi_recorder*.py -v

# Run only new request-only tests
python -m pytest test/test_fastapi_recorder_request_only.py -v

# Run with output
python -m pytest test/test_fastapi_recorder_request_only.py -v -s
```

## Breaking Changes

⚠️ **Note**: If you were relying on response data in collections, this is a breaking change. The decorator now focuses solely on request documentation.

**Migration**: If you need response examples, consider:
1. Manually adding response examples in Postman
2. Using OpenAPI/Swagger documentation instead
3. Creating a separate response capture mechanism

## Future Enhancements

Possible improvements:
- Optional response capture mode (toggle flag)
- Async background recording for zero overhead
- Collection merging/deduplication
- Custom filtering of headers/fields
- Integration with OpenAPI schema

## Questions?

See:
- `test/README_REQUEST_ONLY_TESTS.md` for test details
- `steely/fastapi/README.md` for usage guide
- `examples/fastapi_postman_example.py` for examples
