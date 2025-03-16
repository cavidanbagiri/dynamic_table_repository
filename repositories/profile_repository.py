

import os
import uuid
from io import BytesIO


from sqlalchemy import update
from models.main_models import User as UserModel

from utils.s3_yandex import s3
import aioboto3

class UserProfileImageRepository:
    def __init__(self, db):
        self.db = db

    async def upload_image(self, user_info: dict, file) -> str:
        image_url = await self._upload_file_tostorage(file)
        await self.db.execute(update(UserModel).where(UserModel.id == user_info['id']).values(
            image_url=image_url
        ))
        await self.db.commit()
        return image_url

    async def _upload_file_tostorage(self, file):
        if file:
            file_contents = await file.read()
            user_unique_id = uuid.uuid4()
            suffix = file.filename.split('.')[-1]
            file_path = str(user_unique_id) + '.' + suffix
            s3.upload_fileobj(BytesIO(file_contents), os.getenv('BUCKET_NAME'), 'profile_images/' + file_path)
            image_url = f'https://storage.yandexcloud.net/{os.getenv('BUCKET_NAME')}/profile_images/{file_path}'
            return image_url