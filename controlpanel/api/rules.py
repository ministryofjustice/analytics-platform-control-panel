"""
Rules and permissions (and object permissions) using django-rules
"""

from rules import add_perm, is_active, is_authenticated, is_superuser, predicate

from controlpanel.api.models import (
    App,
    AppS3Bucket,
    Parameter,
    S3Bucket,
    ToolDeployment,
    UserApp,
    UserS3Bucket,
)


@predicate
def is_app_admin(user, obj):
    """
    Check whether `user` is an admin for either;
    - the `obj` `App`
    - the `app` of the `obj` `AppS3Bucket`
    - the `app` of the `obj` `UserApp`

    :param user User: The user to check
    :param obj App|AppS3Bucket|UserApp: The object to check
    """
    if obj is None:
        return True

    if is_superuser(user):
        return True

    if isinstance(obj, App):
        return user in obj.admins

    if isinstance(obj, AppS3Bucket):
        return is_app_admin(user, obj.app)

    if isinstance(obj, UserApp):
        return obj.is_admin

    # XXX raise exception?
    return False


add_perm('api.list_app', is_authenticated)
add_perm('api.create_app', is_authenticated & is_superuser)
add_perm('api.retrieve_app', is_authenticated & is_app_admin)
add_perm('api.update_app', is_authenticated & is_superuser)
add_perm('api.destroy_app', is_authenticated & is_superuser)
add_perm('api.add_app_customer', is_authenticated & is_app_admin)
add_perm('api.remove_app_customer', is_authenticated & is_app_admin)
add_perm('api.add_app_admin', is_authenticated & is_app_admin)
add_perm('api.revoke_app_admin', is_authenticated & is_app_admin)
add_perm('api.add_app_bucket', is_authenticated & is_superuser)
add_perm('api.remove_app_bucket', is_authenticated & is_superuser)
add_perm('api.view_app_logs', is_authenticated & is_app_admin)
add_perm('api.manage_groups', is_authenticated & is_superuser)
add_perm('api.create_policys3bucket', is_authenticated & is_superuser)
add_perm('api.setup_app_auth0', is_authenticated & is_superuser)
add_perm('api.reset_app_secret', is_authenticated & is_superuser)


@predicate
def has_bucket_access(user, obj, **kwargs):
    """
    Check whether `user` has access to;
    - the `obj` `S3Bucket`
    - the `s3bucket` of the `obj` `AppS3Bucket`
    - the `s3bucket` of the `obj` `UserS3Bucket`

    :param user User: The user to check
    :param obj AppS3Bucket|S3Bucket|UserS3Bucket: The object to check
    :param kwargs dict: Additional search criteria
    """
    if obj is None:
        return True

    if isinstance(obj, S3Bucket):
        try:
            UserS3Bucket.objects.get(user=user, s3bucket=obj, **kwargs)
        except UserS3Bucket.DoesNotExist:
            return False
        return True

    if isinstance(obj, AppS3Bucket) or isinstance(obj, UserS3Bucket):
        return has_bucket_access(user, obj.s3bucket)

    # XXX raise exception?
    return False


@predicate
def has_bucket_write_access(user, obj):
    return has_bucket_access(user, obj, access_level=UserS3Bucket.READWRITE)


@predicate
def is_bucket_admin(user, obj):

    if obj is None:
        return True

    if isinstance(obj, S3Bucket):
        return has_bucket_access(user, obj, is_admin=True)

    if isinstance(obj, AppS3Bucket) or isinstance(obj, UserS3Bucket):
        return is_bucket_admin(user, obj.s3bucket)

    # XXX raise an exception?
    return False


add_perm('api.list_s3bucket', is_authenticated)
add_perm('api.create_s3bucket', is_authenticated)
add_perm('api.retrieve_s3bucket', is_authenticated & has_bucket_access)
add_perm('api.update_s3bucket', is_authenticated & has_bucket_write_access)
add_perm('api.destroy_s3bucket', is_authenticated & is_bucket_admin)
add_perm('api.add_s3bucket_admin', is_authenticated & is_bucket_admin)
add_perm('api.remove_s3bucket_admin', is_authenticated & is_bucket_admin)
add_perm('api.grant_s3bucket_access', is_authenticated & is_bucket_admin)
add_perm('api.view_s3bucket_logs', is_authenticated & is_bucket_admin)


@predicate
def is_self(user, other):
    """
    Check whether `user` is performing an action on themselves

    :param user User: The user to check
    :param other User: The other user to check
    """
    if other is None:
        return True

    return user == other


add_perm('api.list_user', is_authenticated & is_superuser)
add_perm('api.create_user', is_authenticated & is_superuser)
add_perm('api.retrieve_user', is_authenticated & is_self)
add_perm('api.update_user', is_authenticated & is_self)
add_perm('api.destroy_user', is_authenticated & is_superuser)
add_perm('api.add_superuser', is_authenticated & is_superuser)
add_perm('api.reset_mfa', is_authenticated & is_superuser)


add_perm('api.list_tool_release', is_authenticated & is_superuser)
add_perm('api.create_tool_release', is_authenticated & is_superuser)
add_perm('api.destroy_tool_release', is_authenticated & is_superuser)
add_perm('api.update_tool_release', is_authenticated & is_superuser)


add_perm('api.list_apps3bucket', is_authenticated)
add_perm('api.create_apps3bucket', is_authenticated & is_superuser)
add_perm(
    'api.retrieve_apps3bucket',
    is_authenticated & (is_app_admin | is_bucket_admin),
)
add_perm(
    'api.update_apps3bucket',
    is_authenticated & is_app_admin & is_bucket_admin,
)
add_perm('api.destroy_apps3bucket', is_authenticated & is_superuser)


add_perm('api.list_users3bucket', is_authenticated)
add_perm('api.create_users3bucket', is_authenticated & is_bucket_admin)
add_perm('api.retrieve_users3bucket', is_authenticated & is_bucket_admin)
add_perm('api.update_users3bucket', is_authenticated & is_bucket_admin)
add_perm('api.destroy_users3bucket', is_authenticated & is_bucket_admin)


add_perm('api.list_tool', is_authenticated)
add_perm('api.create_tool', is_authenticated & is_superuser)
add_perm('api.retrieve_tool', is_authenticated & is_superuser)
add_perm('api.update_tool', is_authenticated & is_superuser)
add_perm('api.destroy_tool', is_authenticated & is_superuser)


add_perm('api.list_ip_allowlists', is_authenticated & is_superuser)
add_perm('api.create_ip_allowlists', is_authenticated & is_superuser)
add_perm('api.update_ip_allowlists', is_authenticated & is_superuser)
add_perm('api.destroy_ip_allowlists', is_authenticated & is_superuser)


@predicate
def is_owner(user, obj):
    if obj is None:
        return True

    if isinstance(obj, ToolDeployment):
        return obj.deployment.namespace == user.k8s_namespace

    if isinstance(obj, Parameter):
        return obj.created_by == user

    return False


add_perm('api.list_deployment', is_authenticated)
add_perm('api.create_deployment', is_authenticated)
add_perm('api.retrieve_deployment', is_authenticated & is_owner)
add_perm('api.update_deployment', is_authenticated & is_owner)
add_perm('api.destroy_deployment', is_authenticated & is_owner)


add_perm('api.list_parameter', is_authenticated)
add_perm('api.create_parameter', is_authenticated)
add_perm('api.retrieve_parameter', is_authenticated & is_owner)
add_perm('api.update_parameter', is_authenticated & is_owner)
add_perm('api.destroy_parameter', is_authenticated & is_owner)
