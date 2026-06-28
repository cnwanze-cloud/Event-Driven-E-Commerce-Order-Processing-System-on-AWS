import json
import logging
import os

import boto3
from botocore.exceptions import ClientError

# --------------------------------------------------
# Logging Configuration
# --------------------------------------------------

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# --------------------------------------------------
# AWS Clients
# --------------------------------------------------

sns = boto3.client("sns")

# --------------------------------------------------
# Environment Variables
# --------------------------------------------------

SNS_TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]

# --------------------------------------------------
# Structured Logging Helper
# --------------------------------------------------


def log_event(level, action, **kwargs):
    """
    Write structured JSON logs to CloudWatch.
    """

    log = {
        "service": "NotificationService",
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

        detail_type = event["detail-type"]
        detail = event["detail"]

        order_id = detail.get("orderId")
        customer_id = detail.get("customerId")

        log_event(
            "info",
            "NotificationReceived",
            eventType=detail_type,
            orderId=order_id
        )

        # --------------------------------------------------
        # Order Confirmed
        # --------------------------------------------------

        if detail_type == "InventoryReserved":

            subject = "Order Confirmed"

            message = (
                f"Dear Customer,\n\n"
                f"Your order has been confirmed successfully.\n\n"
                f"Order ID: {order_id}\n"
                f"Customer ID: {customer_id}\n\n"
                f"Our warehouse has reserved your items and "
                f"your order is now being prepared for shipment.\n\n"
                f"Thank you for shopping with us."
            )

        # --------------------------------------------------
        # Payment Failed
        # --------------------------------------------------

        elif detail_type == "PaymentFailed":

            subject = "Payment Failed"

            message = (
                f"Dear Customer,\n\n"
                f"We were unable to process your payment.\n\n"
                f"Order ID: {order_id}\n"
                f"Customer ID: {customer_id}\n\n"
                f"No payment has been received and your order "
                f"has not been completed.\n\n"
                f"Please try again using another payment method.\n\n"
                f"If you continue to experience problems, "
                f"please contact customer support."
            )

        # --------------------------------------------------
        # Ignore Other Events
        # --------------------------------------------------

        else:

            log_event(
                "info",
                "IgnoredEvent",
                eventType=detail_type
            )

            return {
                "statusCode": 200,
                "body": json.dumps({
                    "message": f"Ignored event: {detail_type}"
                })
            }

        # --------------------------------------------------
        # Publish SNS Notification
        # --------------------------------------------------

        log_event(
            "info",
            "PublishingNotification",
            topic=SNS_TOPIC_ARN,
            subject=subject
        )

        response = sns.publish(

            TopicArn=SNS_TOPIC_ARN,

            Subject=subject,

            Message=message

        )

        log_event(
            "info",
            "NotificationSent",
            orderId=order_id,
            messageId=response["MessageId"]
        )

        log_event(
            "info",
            "LambdaCompleted"
        )

        return {

            "statusCode": 200,

            "body": json.dumps({

                "message": "Notification sent successfully."

            })

        }

    except ClientError as e:

        log_event(
            "error",
            "SNSPublishFailed",
            error=str(e)
        )

        raise

    except Exception as e:

        log_event(
            "error",
            "NotificationProcessingFailed",
            error=str(e)
        )

        raise