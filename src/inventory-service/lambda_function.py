import json
import logging
import os

import boto3
from botocore.exceptions import ClientError

# --------------------------------------------------
# Logging
# --------------------------------------------------

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# --------------------------------------------------
# AWS Clients
# --------------------------------------------------

dynamodb = boto3.resource("dynamodb")
eventbridge = boto3.client("events")

# --------------------------------------------------
# Environment Variables
# --------------------------------------------------

INVENTORY_TABLE = os.environ["INVENTORY_TABLE"]
ORDERS_TABLE = os.environ["ORDERS_TABLE"]
EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME", "default")

inventory_table = dynamodb.Table(INVENTORY_TABLE)
orders_table = dynamodb.Table(ORDERS_TABLE)

# --------------------------------------------------
# Structured Logging
# --------------------------------------------------


def log_event(level, action, **kwargs):

    log = {

        "service": "InventoryService",

        "action": action,

        **kwargs

    }

    getattr(logger, level)(json.dumps(log))


# --------------------------------------------------
# Inventory Processor
# --------------------------------------------------


def process_payment_completed(detail):

    order_id = detail["orderId"]
    customer_id = detail["customerId"]

    log_event(
        "info",
        "LoadingOrder",
        orderId=order_id
    )

    order_response = orders_table.get_item(
        Key={
            "OrderID": order_id
        }
    )

    if "Item" not in order_response:
        raise Exception(f"Order {order_id} not found.")

    order = order_response["Item"]
    items = order["Items"]

    unavailable = []

    # ---------------------------------------
    # Check Inventory
    # ---------------------------------------

    for item in items:

        product_id = item["productId"]
        quantity = item["quantity"]

        response = inventory_table.get_item(
            Key={
                "ProductID": product_id
            }
        )

        if "Item" not in response:

            unavailable.append(product_id)

            continue

        stock = response["Item"]["Stock"]

        if stock < quantity:

            unavailable.append(product_id)

    # ---------------------------------------
    # Inventory Unavailable
    # ---------------------------------------

    if unavailable:

        event_type = "InventoryUnavailable"

        event_detail = {

            "orderId": order_id,

            "customerId": customer_id,

            "products": unavailable

        }

        log_event(
            "warning",
            "InventoryUnavailable",
            products=unavailable
        )

    # ---------------------------------------
    # Reserve Inventory
    # ---------------------------------------

    else:

        for item in items:

            inventory_table.update_item(

                Key={
                    "ProductID": item["productId"]
                },

                UpdateExpression="SET Stock = Stock - :qty",

                ConditionExpression="Stock >= :qty",

                ExpressionAttributeValues={
                    ":qty": item["quantity"]
                }

            )

        log_event(
            "info",
            "InventoryReserved",
            orderId=order_id
        )

        event_type = "InventoryReserved"

        event_detail = {

            "orderId": order_id,

            "customerId": customer_id,

            "items": items

        }

    # ---------------------------------------
    # Publish Event
    # ---------------------------------------

    response = eventbridge.put_events(

        Entries=[

            {

                "Source": "inventory",

                "DetailType": event_type,

                "Detail": json.dumps(event_detail),

                "EventBusName": EVENT_BUS_NAME

            }

        ]

    )

    if response["FailedEntryCount"] > 0:
        raise Exception("Failed to publish EventBridge event.")

    log_event(
        "info",
        "InventoryEventPublished",
        eventType=event_type
    )

    return {

        "statusCode": 200,

        "body": json.dumps({

            "message": event_type

        })

    }


# --------------------------------------------------
# Lambda Handler
# --------------------------------------------------


def lambda_handler(event, context):

    log_event(
        "info",
        "LambdaStarted",
        requestId=context.aws_request_id
    )

    try:

        detail_type = event["detail-type"]

        if detail_type == "PaymentCompleted":

            return process_payment_completed(event["detail"])

        log_event(
            "info",
            "IgnoredEvent",
            eventType=detail_type
        )

        return {

            "statusCode": 200,

            "body": json.dumps({

                "message": "Ignored"

            })

        }

    except ClientError as e:

        log_event(
            "error",
            "DynamoDBError",
            error=str(e)
        )

        raise

    except Exception as e:

        log_event(
            "error",
            "InventoryProcessingFailed",
            error=str(e)
        )

        raise