# AWS CDK Demo – Day 2
## What this deploys
| Resource | Details |
|---|---|
| S3 Bucket | Auto-named, destroys cleanly on `cdk destroy` |
| SNS Topic | `s3-upload-notifications` — sends email on upload |
| Lambda Function | Python 3.12, inline code, triggered by S3 PUT |
| S3 Event Notification | Fires on `.csv` uploads (remove filter for all files) |

## Quick Start

### 1 – Prerequisites
```bash
npm install -g aws-cdk          # install CDK CLI
pip install aws-cdk-lib constructs   # install Python libraries
aws configure                   # set your AWS credentials
```

### If AWS is not installed yet
Follow this link to install AWS https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html

### 2 – Set your email
Open `cdk_demo_stack.py` and change line 14:
```python
NOTIFICATION_EMAIL = "your-email@example.com"   # ← change this
```

### 3 – Bootstrap (first time only per account/region)
```bash
cdk bootstrap aws://ACCOUNT_ID/REGION 
```

### 4 – Deploy
```bash
cdk deploy
```
Check your email — AWS will send a **subscription confirmation** you must click before notifications arrive.
# if I get the error as --require approval what is the soolution?


### 5 – Test
Upload any file to the bucket shown in the outputs:
```bash
aws s3 cp test.csv s3://<BucketName>/test.file_extension
```
You should receive an email within seconds.

### 6 – Tear down
```bash
cdk destroy
```

## How it works
```
User uploads file
       │
       ▼
  S3 Bucket  ──PutObject event──▶  Lambda Function
                                        │
                                        ▼
                                   SNS Topic  ──▶  Email
```
