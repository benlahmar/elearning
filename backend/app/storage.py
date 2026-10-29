import os

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


class Storage:
    def __init__(self):
        self.bucket = os.getenv('S3_BUCKET', 'learning-private')
        options = dict(aws_access_key_id=os.environ['S3_ACCESS_KEY'], aws_secret_access_key=os.environ['S3_SECRET_KEY'], region_name='us-east-1', config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}, connect_timeout=5, read_timeout=30))
        self.internal = boto3.client('s3', endpoint_url=os.environ['S3_ENDPOINT'], **options)
        self.public = boto3.client('s3', endpoint_url=os.environ['S3_PUBLIC_ENDPOINT'], **options)

    def upload(self, file, key, content_type):
        try:
            self.internal.head_bucket(Bucket=self.bucket)
        except ClientError as error:
            if error.response['Error']['Code'] not in ('404', 'NoSuchBucket'):
                raise
            try:
                self.internal.create_bucket(Bucket=self.bucket)
            except ClientError as create_error:
                if create_error.response['Error']['Code'] != 'BucketAlreadyOwnedByYou':
                    raise
        self.internal.upload_fileobj(file, self.bucket, key, ExtraArgs={'ContentType': content_type})

    def access_url(self, key):
        return self.public.generate_presigned_url('get_object', Params={'Bucket': self.bucket, 'Key': key}, ExpiresIn=300)


def get_storage():
    return Storage()
