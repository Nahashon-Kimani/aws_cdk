import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_lambda as _lambda,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
    aws_s3_notifications as s3n,
    aws_iam as iam,
)
from constructs import Construct

# ─────────────────────────────────────────────
#  CHANGE THIS to the email that should receive
#  SNS notifications when a file is uploaded.
# ─────────────────────────────────────────────
NOTIFICATION_EMAIL = "your-email@example.com"


class CdkDemoStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── 1. S3 BUCKET ─────────────────────────────────────────────────────
        bucket = s3.Bucket(
            self, # whast does self refer to here? 
            "DemoBucket",
            bucket_name=None,                           # CDK auto-generates a unique name
            removal_policy=cdk.RemovalPolicy.DESTROY,   # easy teardown in demo. 
            auto_delete_objects=True,                   # empties bucket before deletion
            versioned=False,
        )

        # ── 2. SNS TOPIC + EMAIL SUBSCRIPTION ────────────────────────────────
        topic = sns.Topic(
            self,
            "UploadNotificationTopic",
            display_name="S3 Upload Notifications",
            topic_name="s3-upload-notifications",
        )

        topic.add_subscription(
            subscriptions.EmailSubscription(NOTIFICATION_EMAIL)
        )

        # ── 3. LAMBDA FUNCTION (code embedded inline) ─────────────────────────
        #    Triggered by any S3 upload. Extracts full object metadata from the
        #    event and publishes a rich notification message to SNS.
        lambda_fn = _lambda.Function(
            self,
            "S3UploadHandler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=_lambda.Code.from_inline(
                """
import json
import boto3
import os
import urllib.parse

sns_client = boto3.client("sns")
s3_client  = boto3.client("s3")
SNS_TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]

def handler(event, context):
    print("Event received:", json.dumps(event))

    for record in event.get("Records", []):

        # ── Basic metadata from the S3 event ──────────────────────────────
        event_time  = record.get("eventTime", "N/A")
        event_name  = record.get("eventName", "N/A")
        aws_region  = record.get("awsRegion", "N/A")

        bucket_name = record["s3"]["bucket"]["name"]
        bucket_arn  = record["s3"]["bucket"]["arn"]

        # Object key may be URL-encoded (e.g. spaces become +)
        object_key  = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
        object_size = record["s3"]["object"].get("size", 0)
        etag        = record["s3"]["object"].get("eTag", "N/A")
        version_id  = record["s3"]["object"].get("versionId", "N/A")
        sequencer   = record["s3"]["object"].get("sequencer", "N/A")

        # ── Extended metadata from S3 HeadObject ──────────────────────────
        content_type    = "N/A"
        last_modified   = "N/A"
        storage_class   = "N/A"
        server_side_enc = "N/A"

        try:
            head = s3_client.head_object(Bucket=bucket_name, Key=object_key)
            content_type    = head.get("ContentType", "N/A")
            last_modified   = str(head.get("LastModified", "N/A"))
            storage_class   = head.get("StorageClass", "STANDARD")
            server_side_enc = head.get("ServerSideEncryption", "None")
        except Exception as e:
            print(f"Could not call HeadObject: {e}")

        # ── Human-readable file size ───────────────────────────────────────
        if object_size < 1024:
            size_str = f"{object_size} B"
        elif object_size < 1024 ** 2:
            size_str = f"{object_size / 1024:.2f} KB"
        else:
            size_str = f"{object_size / (1024 ** 2):.2f} MB"

        # ── Build the notification message ────────────────────────────────
        message = (
            f"A new file was uploaded to S3.\\n"
            f"{'=' * 48}\\n\\n"
            f"EVENT DETAILS\\n"
            f"  Event Type  : {event_name}\\n"
            f"  Event Time  : {event_time}\\n"
            f"  AWS Region  : {aws_region}\\n\\n"
            f"BUCKET\\n"
            f"  Name        : {bucket_name}\\n"
            f"  ARN         : {bucket_arn}\\n\\n"
            f"OBJECT\\n"
            f"  Key         : {object_key}\\n"
            f"  Size        : {size_str}\\n"
            f"  ETag        : {etag}\\n"
            f"  Version ID  : {version_id}\\n"
            f"  Sequencer   : {sequencer}\\n\\n"
            f"OBJECT PROPERTIES\\n"
            f"  Content Type      : {content_type}\\n"
            f"  Last Modified     : {last_modified}\\n"
            f"  Storage Class     : {storage_class}\\n"
            f"  Server-Side Enc.  : {server_side_enc}\\n\\n"
            f"  S3 URL: https://{bucket_name}.s3.{aws_region}.amazonaws.com/{object_key}\\n"
        )

        print(message)

        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"S3 Upload: {object_key} ({size_str})",
            Message=message,
        )

    return {"statusCode": 200, "body": "Notifications sent"}
"""
            ),
            environment={
                "SNS_TOPIC_ARN": topic.topic_arn,
            },
            timeout=cdk.Duration.seconds(30),
            description="Triggered on any S3 upload — publishes rich metadata to SNS",
        )

        # Grant Lambda permission to publish to SNS
        topic.grant_publish(lambda_fn)

        # Grant Lambda permission to call HeadObject on the bucket
        bucket.grant_read(lambda_fn)

        # ── 4. S3 EVENT TRIGGER (ANY upload → Lambda) ─────────────────────────
        #    OBJECT_CREATED covers PUT, POST, COPY, and multipart uploads.
        #    No key filter — every file type triggers the function.
        bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(lambda_fn),
        )

        # ── 5. OUTPUTS (printed after cdk deploy) ─────────────────────────────
        cdk.CfnOutput(self, "BucketName", value=bucket.bucket_name)
        cdk.CfnOutput(self, "TopicArn",   value=topic.topic_arn)
        cdk.CfnOutput(self, "LambdaName", value=lambda_fn.function_name)
