"""
Example: Using the Curl Recorder Decorator with FastAPI
=======================================================

This example demonstrates how to use the @curl decorator to automatically
generate executable curl commands from FastAPI endpoint requests.

Run this example:
    uvicorn examples.fastapi_curl_example:app --reload

Then test the endpoints:
    curl http://localhost:8000/users/123
    curl -X POST http://localhost:8000/users -H "Content-Type: application/json" -d '{"name": "John", "email": "john@example.com"}'
    curl http://localhost:8000/users?limit=10

The curl commands will be saved to executable shell scripts in ./.curl_scripts/
"""

from fastapi import FastAPI

from steely.fastapi import recorder

app = FastAPI(title="Curl Recorder Demo")


@app.get("/users/{user_id}")
@recorder.curl()
async def get_user(user_id: int):
    """
    Get a specific user by ID.
    Curl commands will be saved to .curl_scripts/get_user.sh
    """
    return {
        "user_id": user_id,
        "name": "John Doe",
        "email": f"user{user_id}@example.com",
        "status": "active"
    }


@app.get("/users")
@recorder.curl(script_name="user_api")
async def list_users(limit: int = 10, offset: int = 0):
    """
    List all users with pagination.
    Curl commands will be saved to .curl_scripts/user_api.sh
    """
    return {
        "users": [
            {"id": i, "name": f"User {i}"}
            for i in range(offset, offset + limit)
        ],
        "total": 100,
        "limit": limit,
        "offset": offset
    }


@app.post("/users")
@recorder.curl(script_name="user_api")
async def create_user(name: str, email: str):
    """
    Create a new user.
    Curl commands will also be saved to .curl_scripts/user_api.sh
    (grouped with list_users)
    """
    return {
        "id": 123,
        "name": name,
        "email": email,
        "status": "active",
        "created_at": "2025-12-10T10:00:00Z"
    }


@app.put("/users/{user_id}")
@recorder.curl(script_name="user_api")
async def update_user(user_id: int, name: str, email: str = None):
    """
    Update a user.
    Curl commands will also be saved to .curl_scripts/user_api.sh
    """
    return {
        "id": user_id,
        "name": name,
        "email": email,
        "updated_at": "2025-12-10T10:00:00Z"
    }


@app.delete("/users/{user_id}")
@recorder.curl(script_name="user_api")
async def delete_user(user_id: int):
    """
    Delete a user.
    Curl commands will also be saved to .curl_scripts/user_api.sh
    """
    return {
        "message": f"User {user_id} deleted successfully",
        "user_id": user_id
    }


# Example with JSON body
@app.post("/users/bulk")
@recorder.curl(script_name="user_api")
async def create_users_bulk(users: list):
    """
    Create multiple users at once.
    Demonstrates curl command generation with JSON body.
    """
    return {
        "created": len(users),
        "users": users
    }


if __name__ == "__main__":
    import uvicorn
    print("""
    Starting FastAPI Curl Recorder Demo...

    After making requests, check the generated curl scripts:
    - .curl_scripts/get_user.sh       (single endpoint)
    - .curl_scripts/user_api.sh       (grouped endpoints)

    You can execute these scripts directly:
    $ bash .curl_scripts/user_api.sh
    """)
    uvicorn.run(app, host="0.0.0.0", port=8000)
