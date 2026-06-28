import json
import uuid
import logging
import os
from datetime import datetime
from decimal import Decimal

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

ORDERS_TABLE = os.environ["ORDERS_TABLE"]
EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME", "default")

table = dynamodb.Table(ORDERS_TABLE)


# --------------------------------------------------
# JSON Encoder (for Decimal)
# --------------------------------------------------

class DecimalEncoder(json.JSONEncoder):

    def default(self, obj):

        if isinstance(obj, Decimal):

            if obj % 1 == 0:
                return int(obj)

            return float(obj)

        return super().default(obj)


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def log(level, action, **kwargs):

    message = {
        "service": "OrderService",
        "action": action,
        **kwargs
    }

    getattr(logger, level)(json.dumps(message))


def response(status_code, body):

    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(body, cls=DecimalEncoder)
    }


# --------------------------------------------------
# Parse Request Body
# --------------------------------------------------

def get_request_body(event):

    body = event.get("body")

    if body is None:
        raise ValueError("Request body is empty.")

    if isinstance(body, dict):
        return body

    return json.loads(
        body,
        parse_float=Decimal
    )


# --------------------------------------------------
# POST /orders
# --------------------------------------------------

def create_order(event):

    body = get_request_body(event)

    customer_id = body["customerId"]
    items = body["items"]
    total = body["totalAmount"]

    order_id = str(uuid.uuid4())

    order = {

        "OrderID": order_id,
        "CustomerID": customer_id,
        "Items": items,
        "Total": total,
        "Status": "Pending",
        "Timestamp": datetime.utcnow().isoformat()

    }

    table.put_item(Item=order)

    log(
        "info",
        "OrderCreated",
        orderId=order_id
    )

    response_event = eventbridge.put_events(

        Entries=[
            {
                "Source": "orders",
                "DetailType": "OrderCreated",
                "Detail": json.dumps({
                    "orderId": order_id,
                    "customerId": customer_id,
                    "items": items
                }),
                "EventBusName": EVENT_BUS_NAME
            }
        ]

    )

    log(
        "info",
        "OrderCreatedEventPublished",
        orderId=order_id,
        eventId=response_event["Entries"][0].get("EventId")
    )

    return response(201, order)


# --------------------------------------------------
# GET /orders
# --------------------------------------------------

def get_orders():

    result = table.scan()

    return response(
        200,
        result.get("Items", [])
    )


# --------------------------------------------------
# GET /orders/{id}
# --------------------------------------------------

def get_order(order_id):

    result = table.get_item(

        Key={
            "OrderID": order_id
        }

    )

    if "Item" not in result:

        return response(
            404,
            {
                "message": "Order not found."
            }
        )

    return response(
        200,
        result["Item"]
    )


# --------------------------------------------------
# DELETE /orders/{id}
# --------------------------------------------------

def delete_order(order_id):

    result = table.get_item(

        Key={
            "OrderID": order_id
        }

    )

    if "Item" not in result:

        return response(
            404,
            {
                "message": "Order not found."
            }
        )

    table.delete_item(

        Key={
            "OrderID": order_id
        }

    )

    log(
        "info",
        "OrderDeleted",
        orderId=order_id
    )

    return response(
        200,
        {
            "message": "Order deleted successfully."
        }
    )


# --------------------------------------------------
# EventBridge Handler
# --------------------------------------------------

def process_eventbridge(event):

    detail = event["detail"]
    detail_type = event["detail-type"]

    order_id = detail["orderId"]

    if detail_type == "InventoryReserved":

        new_status = "Confirmed"

    elif detail_type == "PaymentFailed":

        new_status = "Payment Failed"

    else:

        log(
            "info",
            "IgnoredEvent",
            eventType=detail_type
        )

        return response(
            200,
            {
                "message": "Event ignored."
            }
        )

    table.update_item(

        Key={
            "OrderID": order_id
        },

        UpdateExpression="SET #status = :status",

        ExpressionAttributeNames={
            "#status": "Status"
        },

        ExpressionAttributeValues={
            ":status": new_status
        }

    )

    log(
        "info",
        "OrderUpdated",
        orderId=order_id,
        status=new_status
    )

    return response(
        200,
        {
            "message": "Order updated successfully."
        }
    )


# --------------------------------------------------
# Lambda Entry Point
# --------------------------------------------------

def lambda_handler(event, context):

    print("========== EVENT ==========")
    print(json.dumps(event, indent=4, default=str))
    print("===========================")

    log(
        "info",
        "LambdaStarted",
        requestId=context.aws_request_id
    )

    try:

        # EventBridge Event
        if "detail-type" in event:

            return process_eventbridge(event)

        method = event.get("httpMethod")
        path_parameters = event.get("pathParameters") or {}
        order_id = path_parameters.get("id")

        # POST /orders
        if method == "POST":

            return create_order(event)

        # GET /orders
        elif method == "GET" and order_id is None:

            return get_orders()

        # GET /orders/{id}
        elif method == "GET" and order_id:

            return get_order(order_id)

        # DELETE /orders/{id}
        elif method == "DELETE" and order_id:

            return delete_order(order_id)

        return response(
            405,
            {
                "message": "Method not allowed."
            }
        )

    except ClientError as e:

        log(
            "error",
            "AWSClientError",
            error=str(e)
        )

        return response(
            500,
            {
                "message": str(e)
            }
        )

    except KeyError as e:

        return response(
            400,
            {
                "message": f"Missing required field: {e.args[0]}"
            }
        )

    except ValueError as e:

        return response(
            400,
            {
                "message": str(e)
            }
        )

    except Exception as e:

        log(
            "error",
            "UnhandledException",
            error=str(e)
        )

        return response(
            500,
            {
                "message": str(e)
            }
        )