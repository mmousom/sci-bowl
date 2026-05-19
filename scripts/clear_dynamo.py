"""One-time script to delete all items from ScienceBowlQuestions table."""

import boto3
from boto3.dynamodb.conditions import Key

TABLE_NAME = "ScienceBowlQuestions"
PROFILE = "onasmmon"
REGION = "us-east-1"

session = boto3.Session(profile_name=PROFILE)
dynamodb = session.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(TABLE_NAME)

print(f"Scanning {TABLE_NAME} for all keys...")

deleted = 0
scan_kwargs = {
    "ProjectionExpression": "Set_Round, Question_Id",
}

while True:
    response = table.scan(**scan_kwargs)
    items = response.get("Items", [])

    # Batch delete in groups of 25
    with table.batch_writer() as batch:
        for item in items:
            batch.delete_item(Key={
                "Set_Round": item["Set_Round"],
                "Question_Id": item["Question_Id"],
            })
            deleted += 1

    print(f"  Deleted {deleted} items so far...")

    last_key = response.get("LastEvaluatedKey")
    if not last_key:
        break
    scan_kwargs["ExclusiveStartKey"] = last_key

print(f"Done. Total deleted: {deleted}")
