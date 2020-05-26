"""
Reads all the current buckets, ensures that versioning is switched on for those
that don't yet have it and sets the life cycle configuration to send
non-current versions of files to glacier storage after 30 days.
"""
import boto3


s3 = boto3.client('s3')
buckets = s3.list_buckets()
for bucket_dict in buckets["Buckets"]:
    bucket_name = bucket_dict["Name"]
    print("Working on {bucket_name}.")
    bucket = boto3.resource("s3").Bucket(bucket_name)
    # Add versioning if not already set.
    versioning = bucket.Versioning()
    if not versioning.status == "Enabled":
        print("Enabling versioning for {bucket_name}.")
        versioning.enable()
    # Set life cycle rule to send non-current versions of files to glacier
    # storage after 30 days.
    lifecycle_id = f"{bucket_name}_lifecycle_configuration"
    print("Setting lifecycle {lifecycle_id} for bucket {bucket_name}.")
    lifecycle_conf = boto3.client("s3").put_bucket_lifecycle_configuration(
        Bucket=bucket_name,
        LifecycleConfiguration={
            "Rules": [
                {
                    "ID": lifecycle_id,
                    "Status": "Enabled",
                    "Prefix": "",
                    "NoncurrentVersionTransitions": [
                        {
                            'NoncurrentDays': 30,
                            'StorageClass': 'GLACIER',
                        },
                    ]
                },
            ]
        }
    )
