




import pytest
import requests
from schemas.main_model_schemas import RegisterResponseSchema, ResponseRegisterUserSchema

endpoint: str = "http://localhost:8000/api/user/register"

class TestUserRegister:

    def test_user_register(self):
        data = {
            "name": "cavidan",
            "username": "ramzes6",
            "email": "cavidanbagiri6@gmail.com",
            "password": "cavidan1"
        }
        response = requests.post(endpoint, json=data)

        # Assertions for status code and message
        assert response.status_code == 201, f"Expected status code 201, got {response.status_code}"
        response_data = response.json()
        assert response_data["message"] == "User registered successfully", "Unexpected success message"

        # Validate the user data against the schema
        user_data = response_data["user"]
        try:
            parsed_user = ResponseRegisterUserSchema(**user_data)
            # Compare the dictionary representation of the Pydantic model
            assert user_data == parsed_user.dict(), "User data does not match the schema"
        except Exception as e:
            pytest.fail(f"Failed to validate user data: {e}")
