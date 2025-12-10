"""
Example: Using Both Postman and Curl Recorders Together
========================================================

This example demonstrates how to use both @postman and @curl decorators
together on the same endpoints for maximum flexibility.

Run this example:
    uvicorn examples.fastapi_combined_recorders:app --reload

Then test the endpoints:
    curl http://localhost:8000/users/123
    curl -X POST http://localhost:8000/users -H "Content-Type: application/json" -d '{"name": "John", "email": "john@example.com"}'

You'll get:
- Postman collections in ./.postman_collections/
- Curl scripts in ./.curl_scripts/
"""

from fastapi import FastAPI

from steely.fastapi import recorder, postman

app = FastAPI(title="Combined Recorders Demo")


# Using both decorators on the same endpoint
@app.get("/users/{user_id}")
@recorder.curl(script_name="user_api")
@recorder.postman(collection_name="user_api")
async def get_user(user_id: int, include_details: bool = False):
    """
    Get a specific user by ID.

    This will generate:
    - Curl command in .curl_scripts/user_api.sh
    - Postman collection in .postman_collections/user_api.json
    """
    user = {
        "user_id": user_id,
        "name": "John Doe",
        "email": f"user{user_id}@example.com",
    }

    if include_details:
        user.update({
            "created_at": "2025-01-01T00:00:00Z",
            "last_login": "2025-12-10T10:00:00Z",
            "status": "active"
        })

    return user


@app.get("/users")
@recorder.curl(script_name="user_api")
@recorder.postman(collection_name="user_api")
async def list_users(limit: int = 10, offset: int = 0, search: str = None):
    """
    List users with pagination and search.

    Both decorators record to the same grouped files.
    """
    users = [
        {"id": i, "name": f"User {i}", "email": f"user{i}@example.com"}
        for i in range(offset, offset + limit)
    ]

    if search:
        users = [u for u in users if search.lower() in u["name"].lower()]

    return {
        "users": users,
        "total": 100,
        "limit": limit,
        "offset": offset
    }


@app.post("/users")
@recorder.curl(script_name="user_api")
@recorder.postman(collection_name="user_api")
async def create_user(name: str, email: str, age: int = None):
    """
    Create a new user.

    POST requests with body - perfect for comparing curl vs Postman format.
    """
    return {
        "id": 123,
        "name": name,
        "email": email,
        "age": age,
        "status": "active",
        "created_at": "2025-12-10T10:00:00Z"
    }


@app.put("/users/{user_id}")
@recorder.curl(script_name="user_api")
@recorder.postman(collection_name="user_api")
async def update_user(user_id: int, name: str = None, email: str = None):
    """
    Update a user.

    PUT requests demonstrate both formats nicely.
    """
    updates = {}
    if name:
        updates["name"] = name
    if email:
        updates["email"] = email

    return {
        "id": user_id,
        **updates,
        "updated_at": "2025-12-10T10:00:00Z"
    }


@app.delete("/users/{user_id}")
@recorder.curl(script_name="user_api")
@recorder.postman(collection_name="user_api")
async def delete_user(user_id: int):
    """
    Delete a user.

    DELETE requests are straightforward in both formats.
    """
    return {
        "message": f"User {user_id} deleted successfully",
        "user_id": user_id,
        "deleted_at": "2025-12-10T10:00:00Z"
    }


# Example: Different recorders for different purposes
@app.get("/admin/stats")
@recorder.curl(script_name="admin_curl_only")
async def get_admin_stats():
    """
    This endpoint only uses curl recorder.
    Perfect for internal/admin endpoints that need CLI access.
    """
    return {
        "total_users": 1000,
        "active_users": 850,
        "total_requests": 50000
    }


@app.get("/public/health")
@recorder.postman(collection_name="public_api")
async def health_check():
    """
    This endpoint only uses Postman recorder.
    Perfect for public APIs that will be shared via Postman.
    """
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": "2025-12-10T10:00:00Z"
    }


if __name__ == "__main__":
    import uvicorn

    print("""
    🚀 Starting Combined Recorders Demo...

    After making requests, check the generated files:

    📝 Curl Scripts:
    - .curl_scripts/user_api.sh       (User endpoints)
    - .curl_scripts/admin_curl_only.sh (Admin endpoints)

    📦 Postman Collections:
    - .postman_collections/user_api.json    (User endpoints)
    - .postman_collections/public_api.json  (Public endpoints)

    💡 Usage:

    # Run curl commands directly:
    $ bash .curl_scripts/user_api.sh

    # Or execute individual commands:
    $ curl "http://localhost:8000/users/42"

    # Import Postman collections:
    1. Open Postman
    2. Click Import
    3. Select .postman_collections/user_api.json

    🎯 Benefits of using both:
    - Curl: CLI testing, CI/CD, quick debugging
    - Postman: GUI testing, team sharing, documentation
    """)

    uvicorn.run(app, host="0.0.0.0", port=8000)
