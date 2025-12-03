# lifted from https://stackoverflow.com/questions/50003378/automatically-set-listenerrule-priority-in-cloudformation-template
import json
import os
import random
import uuid

import boto3
import urllib3

SUCCESS = "SUCCESS"
FAILED = "FAILED"
# Member must have value less than or equal to 50000
ALB_RULE_PRIORITY_RANGE = 1, 50000


def lambda_handler(event, context):
    try:
        _lambda_handler(event, context)
    except Exception as e:
        # Must raise, otherwise the Lambda will be marked as successful, and the exception
        # will not be logged to CloudWatch logs.
        # Always send a response otherwise custom resource creation/update/deletion will be stuck
        send(
            event,
            context,
            response_status=FAILED if event["RequestType"] != "Delete" else SUCCESS,
            # Do not fail on delete to avoid rollback failure
            response_data=None,
            physical_resource_id=uuid.uuid4(),
            reason=e,
        )
        raise


def _lambda_handler(event, context):
    print(json.dumps(event))

    physical_resource_id = event.get("PhysicalResourceId", str(uuid.uuid4()))
    response_data = {}

    if event["RequestType"] == "Create":
        elbv2_client = boto3.client("elbv2")
        result = elbv2_client.describe_rules(ListenerArn=os.environ["ListenerArn"])

        in_use = list(filter(lambda s: s.isdecimal(), [r['Priority'] for r in result['Rules']]))

        priority = None
        while not priority or priority in in_use:
            priority = str(random.randint(*ALB_RULE_PRIORITY_RANGE))

        response_data = {"Priority": priority}

    send(event, context, SUCCESS, response_data, physical_resource_id)


def send(event, context, response_status, response_data, physical_resource_id, reason=None):
    response_url = event["ResponseURL"]

    http = urllib3.PoolManager()

    body = {
        "Status": response_status,
        "Reason": reason or "See the details in CloudWatch Log Stream: " + context.log_stream_name,
        "PhysicalResourceId": physical_resource_id,
        "StackId": event["StackId"],
        "RequestId": event["RequestId"],
        "LogicalResourceId": event["LogicalResourceId"],
        "Data": response_data,
    }
    encoded_body = json.dumps(body).encode("utf-8")
    headers = {
        "content-type": "",
        "content-length": str(len(encoded_body)),
    }

    http.request("PUT", response_url, body=encoded_body, headers=headers)
