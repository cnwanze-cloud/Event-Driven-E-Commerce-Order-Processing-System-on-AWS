# Event-Driven Order Processing System on AWS
## Goal

Build a scalable serverless e-commerce backend where every service is independent and communicates through events instead of direct API calls.

### Instead of:
```
Order Service ───> Payment Service
```
Everything communicates through events:
```
Customer ───> API Gateway ───> Lambda (Order Service) ───> EventBridge ───┬───> Payment ───> SNS
                                                                          └───> Inventory ───> SQS
```
---

## Architecture
```
                              Client
                                 │
                            API Gateway
                                 │
                            Order Lambda
                                 │
                       PutEvents(EventBridge)
                                 │
           ┌─────────────────────┼─────────────────────┐
           │                     │                     │
    Payment Lambda       Inventory Lambda     Notification Lambda
           │                     │                     │
       DynamoDB              DynamoDB                 SNS
                                 │
                             SQS Queue
                                 │
                         Dead Letter Queue
```
<img width="1408" height="768" alt="Architecture" src="https://github.com/user-attachments/assets/6e3bdb2b-5a11-470b-9e31-4a10eb6cc789" />


---
## Technologies

- AWS API Gateway
- AWS Lambda
- Amazon EventBridge
- Amazon DynamoDB
- Amazon SNS
- Amazon SQS
- CloudWatch
- IAM
- Terraform
- GitHub Actions
- Python
- Boto3
- Pytest

---

## Folder Structure

```
event-driven-ecommerce/
│
├── docs/
│   ├── architecture.png
│   ├── screenshots/
│
│
├── services/
    ├── orders/
    │   ├── lambda_function.py
    │   └── requirements.txt
    ├── payments/
    │   └── lambda_function.py
    ├── inventory/
    │   └── lambda_function.py
    └── notifications/
       └── lambda_function.py
```

---
## Implementation Steps

### Step 1: Create DynamoDB Tables

Instead of one table, create three:

* **Orders Table**

  * `OrderID` (Partition Key)
  * `Status`
  * `Items`
  * `Total`
  * `Timestamp`

* **Inventory Table**

  * `ProductID` (Partition Key)
  * `Stock`
  * `Price`

* **Payments Table**

  * `PaymentID` (Partition Key)
  * `OrderID`
  * `Status`
  * `Amount`

### Step 2: Create REST APIs

Create the following API endpoints:

* `POST /orders`
* `GET /orders/{id}`
* `DELETE /orders/{id}`

> **Note:** Only the **Order Service** is exposed publicly. All other services communicate internally through events.

### Step 3: Create Order Lambda

**Responsibilities**

* Receive incoming requests
* Validate the request payload
* Generate a unique Order ID
* Save the order to DynamoDB
* Publish an `OrderCreated` event to Amazon EventBridge

**Example Client Payload**

```json
{
  "customerId": "123",
  "items": [
    {
      "productId": "P100",
      "quantity": 2
    }
  ]
}
```
**Example Published Event**
```json
{
  "source": "orders",
  "detail-type": "OrderCreated",
  "detail": {
      "orderId": "123",
      "customerId": "999",
      "items": [...]
  }
}
```

---

### Step 4: Configure EventBridge

Create an EventBridge rule with the following configuration:

* **Rule:** Trigger when `detail-type` = `OrderCreated`
* **Targets:**

  * Payment Lambda
  * Inventory Lambda
  * Notification Lambda

> Every service reacts independently to the same event, enabling a loosely coupled architecture.

### Step 5: Payment Service

The Payment Service:

* Receives the `OrderCreated` event
* Simulates a payment (`Success` or `Failure`)
* Stores the payment record in the **Payments** table
* Publishes either:

  * `PaymentCompleted`, or
  * `PaymentFailed`

### Step 6: Inventory Service

The Inventory Service:

* Receives the `OrderCreated` event
* Checks product inventory

If inventory is available:

* Reduce stock
* Publish `InventoryReserved`

If inventory is unavailable:

* Publish `InventoryUnavailable`

### Step 7: Notification Service

The Notification Service:

* Receives the `PaymentCompleted` and `InventoryReserved` events
* Publishes an SNS notification indicating:

```
Order Confirmed
```

### Step 8: Add SQS

Instead of EventBridge invoking the Payment Lambda directly, introduce Amazon SQS:

```text
EventBridge
      │
      ▼
     SQS
      │
      ▼
Payment Lambda
```

**Benefits**

* Automatic retries
* Service decoupling
* Handles back pressure
* Prevents lost events

### Step 9: Dead Letter Queue (DLQ)

If payment processing fails after all retry attempts:

```text
Payment Queue
      │
      ▼
     DLQ
      │
      ▼
CloudWatch Alarm
      │
      ▼
   SNS Email
```

> This is a common production architecture pattern for handling failed messages.

### Step 10: CloudWatch

Create CloudWatch alarms for:

* Lambda Errors
* Lambda Duration
* Lambda Throttles
* DLQ Messages
* API Gateway 5XX Errors
* API Latency

### Step 11: Structured Logging

Instead of using:

```python
print(event)
```

Use structured JSON logging:

```python
logger.info(
    {
        "orderId": order_id,
        "status": "Pending"
    }
)
```

> Structured logs make searching, filtering, and monitoring much easier using CloudWatch Logs Insights.

---

### Step 12: Add X-Ray

Enable AWS X-Ray tracing to visualize the end-to-end execution flow:

```text
API
  │
  ▼
Lambda
  │
  ▼
EventBridge
  │
  ▼
Lambda
  │
  ▼
DynamoDB
```

---

### Step 13: Error Handling

Handle failures gracefully throughout the system.

**Example:** Payment processing fails.

Actions to take:

* Publish a `PaymentFailed` event.
* **Notification Service:** Send an email to the customer.
* **Order Service:** Update the order status.
* **Inventory Service:** Roll back the reserved stock.

---

### Step 15: Integration Testing

Create a Postman Collection to verify the complete workflow:

```text
Create Order
      │
      ▼
Verify Order
      │
      ▼
Simulate Payment
      │
      ▼
Inventory Updated
      │
      ▼
SNS Sent
```

---

### Step 16: Monitoring Dashboard

Create a CloudWatch Dashboard with widgets for:

* Lambda Invocations
* Lambda Errors
* Lambda Latency
* DynamoDB Reads
* DynamoDB Writes
* API Requests
* DLQ Messages

---

## Event Flow

```
Customer
   │
   ▼
POST /orders
   │
   ▼
API Gateway
   │
   ▼
Order Lambda ───> Orders Table
   │
   ▼
EventBridge
   │
   ▼
OrderCreated Event
   │
   ├──────────────────────────────┬──────────────────────────────┐
   │                              │                              │
   ▼                              ▼                              ▼
Payment Lambda             Inventory Lambda              Notification Lambda
   │                              │                              │
   ▼                              ▼                              ▼
Payments DB                   Inventory DB                      SNS
   │
   ▼
PaymentCompleted Event
   │
   ▼
EventBridge
   │
   ▼
Order Service
   │
   ▼
Order Status Updated
```
