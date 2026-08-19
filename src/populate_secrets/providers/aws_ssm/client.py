import boto3


def ssm_client():
    return boto3.client("ssm")


def aws_session():
    return boto3.session.Session()
