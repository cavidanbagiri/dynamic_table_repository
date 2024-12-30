import os

from fastapi import HTTPException

from fastapi import Request

# Import JWT
import jwt

ACCESS_TOKEN_EXPIRE_MINUTES = 30

class TokenVerifyMiddleware:

    # Verify Access Token
    @staticmethod
    def verify_access_token(request: Request):
        headers = dict(request.headers)
        print(f'the headers are {headers}')
        if headers.get('token'):
            try:
                payload = jwt.decode(headers['token'], os.getenv('JWT_SECRET_KEY'), algorithms=os.getenv('JWT_ALGORITHM'))
                return payload
            except jwt.ExpiredSignatureError:
                raise HTTPException(status_code=401, detail="Invalid token")
            except jwt.DecodeError:
                raise HTTPException(status_code=401, detail="Invalid token")
        else:
            raise HTTPException(status_code=401, detail="Invalid token")