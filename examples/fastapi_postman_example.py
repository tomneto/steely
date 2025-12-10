"""
Example: Using the Postman Recorder Decorator with FastAPI
==========================================================

This example demonstrates how to use the @postman decorator to automatically
record FastAPI endpoint requests and responses to Postman Collection format.

Run this example:
    uvicorn examples.fastapi_postman_example:app --reload

Then test the endpoints:
    curl http://localhost:8000/users/123
    curl -X POST http://localhost:8000/users -H "Content-Type: application/json" -d '{"name": "John", "email": "john@example.com"}'
    curl http://localhost:8000/users?limit=10

The Postman collections will be saved to ./postman_collections/
"""

from fastapi import FastAPI

from steely.fastapi import postman

app = FastAPI(title="Postman Recorder Demo")


@app.get("/users/{user_id}")
@postman()
async def get_user(user_id: int):
    """
    Get a specific user by ID.
    This endpoint will be recorded to postman_collections/get_user.json
    """
    return {
        "user_id": user_id,
        "name": "John Doe",
        "email": f"user{user_id}@example.com",
        "status": "active"
    }


@app.get("/users")
@postman(collection_name="user_api")
async def list_users(limit: int = 10, offset: int = 0):
    """
    List all users with pagination.
    This endpoint will be recorded to postman_collections/user_api.json
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
@postman(collection_name="user_api")
async def create_user(name: str, email: str):
    """
    Create a new user.
    This endpoint will also be recorded to postman_collections/user_api.json
    (same collection as list_users)
    """
    return {
        "id": 123,
        "name": name,
        "email": email,
        "status": "active",
        "created_at": "2025-12-10T10:00:00Z"
    }


@app.delete("/users/{user_id}")
@postman(collection_name="user_api")
async def delete_user(user_id: int):
    """
    Delete a user.
    This endpoint will also be recorded to postman_collections/user_api.json
    """
    return {
        "message": f"User {user_id} deleted successfully",
        "user_id": user_id
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
