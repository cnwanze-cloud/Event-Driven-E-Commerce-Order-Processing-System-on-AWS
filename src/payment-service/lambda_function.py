import json
import uuid
import random
import logging
import os
from datetime import datetime

import boto3

# --------------------------------------------------
# Logging Configuration
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

PAYMENTS_TABLE = os.environ["PAYMENTS_TABLE"]
EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME", "default")

table = dynamodb.Table(PAYMENTS_TABLE)


# --------------------------------------------------
# Helper Function for Structured Logging
# --------------------------------------------------

def log_event(level, action, **kwargs):
    """
    Creates structured JSON logs.
    """

    log = {
        "service": "PaymentService",
        "action": action,
        **kwargs
    }

    getattr(logger, level)(json.dumps(log))


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

        # --------------------------------------------------
        # Process every SQS message
        # --------------------------------------------------

        for record in event["Records"]:

            body = json.loads(record["body"])

            log_event(
                "info",
                "SQSMessageReceived",
                body=body
            )

            # --------------------------------------------------
            # EventBridge Event
            # --------------------------------------------------

            detail = body["detail"]

            order_id = detail["orderId"]
            customer_id = detail["customerId"]

            log_event(
                "info",
                "PaymentProcessingStarted",
                orderId=order_id,
                customerId=customer_id
            )

            # --------------------------------------------------
            # Simulate Payment
            # --------------------------------------------------

            payment_success = random.choice(
                [True, True, True, True, False]
            )

            payment_status = (
                "Successful"
                if payment_success
                else "Failed"
            )

            payment_id = str(uuid.uuid4())

            payment = {

                "PaymentID": payment_id,

                "OrderID": order_id,

                "CustomerID": customer_id,

                "Status": payment_status,

                "Amount": 0,

                "Timestamp": datetime.utcnow().isoformat()

            }

            # --------------------------------------------------
            # Save Payment
            # --------------------------------------------------

            log_event(
                "info",
                "SavingPayment",
                paymentId=payment_id,
                orderId=order_id
            )

            response = table.put_item(Item=payment)

            log_event(
                "info",
                "PaymentSaved",
                paymentId=payment_id,
                statusCode=response["ResponseMetadata"]["HTTPStatusCode"]
            )

            # --------------------------------------------------
            # Decide Event Type
            # --------------------------------------------------

            if payment_success:

                event_type = "PaymentCompleted"

            else:

                event_type = "PaymentFailed"

            # --------------------------------------------------
            # Publish EventBridge Event
            # --------------------------------------------------

            event_payload = {

                "Source": "payments",

                "DetailType": event_type,

                "Detail": json.dumps({

                    "paymentId": payment_id,

                    "orderId": order_id,

                    "customerId": customer_id,

                    "status": payment_status

                }),

                "EventBusName": EVENT_BUS_NAME

            }

            log_event(
                "info",
                "PublishingEvent",
                eventType=event_type,
                orderId=order_id
            )

            response = eventbridge.put_events(
                Entries=[event_payload]
            )

            if response["FailedEntryCount"] > 0:

                log_event(
                    "error",
                    "EventBridgePublishFailed",
                    response=response
                )

                raise Exception(
                    "Failed to publish EventBridge event."
                )

            log_event(
                "info",
                "EventPublished",
                eventType=event_type,
                eventId=response["Entries"][0]["EventId"]
            )

            log_event(
                "info",
                "PaymentProcessingCompleted",
                paymentId=payment_id,
                orderId=order_id,
                status=payment_status
            )

        # --------------------------------------------------
        # Success
        # --------------------------------------------------

        log_event(
            "info",
            "LambdaCompleted"
        )

        return {

            "statusCode": 200,

            "body": json.dumps({

                "message": "Payment processed successfully."

            })

        }

    except Exception as e:

        log_event(
            "error",
            "PaymentProcessingFailed",
            error=str(e)
        )

        raise