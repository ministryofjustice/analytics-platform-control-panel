# First-party/Local
from controlpanel import celery_app
from controlpanel.api.tasks.handlers.app import CreateAppAuthSettings, CreateAppAWSRole
from controlpanel.api.tasks.handlers.s3 import (
    CreateS3Bucket,
    GrantAppS3BucketAccess,
    GrantUserS3BucketAccess,
    S3BucketRevokeAllAccess,
    S3BucketRevokeAppAccess,
    S3BucketRevokeUserAccess,
)

create_app_aws_role = celery_app.register_task(CreateAppAWSRole())
create_s3bucket = celery_app.register_task(CreateS3Bucket())
grant_app_s3bucket_access = celery_app.register_task(GrantAppS3BucketAccess())
grant_user_s3bucket_access = celery_app.register_task(GrantUserS3BucketAccess())
create_app_auth_settings = celery_app.register_task(CreateAppAuthSettings())
revoke_user_s3bucket_access = celery_app.register_task(S3BucketRevokeUserAccess())
revoke_app_s3bucket_access = celery_app.register_task(S3BucketRevokeAppAccess())
revoke_all_access_s3bucket = celery_app.register_task(S3BucketRevokeAllAccess())
