# Event-Driven Order Processing System on AWS

A production-inspired, serverless event-driven order processing system built on AWS using **Amazon API Gateway**, **AWS Lambda**, **Amazon EventBridge**, **Amazon SQS**, **Amazon DynamoDB**, **Amazon CloudWatch**, and **IAM**.

The project demonstrates how modern cloud-native microservices communicate asynchronously using events rather than direct service-to-service calls.

---

# Overview

This project simulates the backend of an e-commerce platform where creating an order automatically triggers downstream business processes without tightly coupling services.

The architecture follows an **event-driven microservices pattern**, where each service is responsible for a single business capability.

## Workflow

1. Client submits an order through API Gateway.
2. Order Service validates and stores the order in DynamoDB.
3. Order Service publishes an `OrderCreated` event to Amazon EventBridge.
4. EventBridge routes the event to Amazon SQS.
5. Payment Service consumes the message from SQS.
6. Payment Service processes the payment.
7. Payment Service stores payment information in DynamoDB.
8. Payment Service publishes a `PaymentCompleted` event.
9. Additional services can subscribe to future events without modifying existing services.

---

# Architecture

```text
                    +------------------+
                    |     Postman      |
                    +--------+---------+
                             |
                             |
                    Amazon API Gateway
                             |
                             |
                     Order Lambda Service
                             |
          +------------------+------------------+
          |                                     |
          |                                     |
          ▼                                     ▼
 Orders DynamoDB                      Amazon EventBridge
                                              |
                                              |
                                       EventBridge Rule
                                              |
                                              |
                                          Amazon SQS
                                              |
                                              |
                                    Payment Lambda Service
                                              |
                    +-------------------------+---------------------+
                    |                                               |
                    ▼                                               ▼
            Payments DynamoDB                      PaymentCompleted Event
                                                           |
                                                           |
                                                    Amazon EventBridge
                                                           |
                                      (Inventory • Shipping • Email • Analytics)
```

<img width="1536" height="1024" alt="Architecture" src="https://github.com/user-attachments/assets/1aa8886d-d269-404e-b628-badc5a30a7d3" />


---

# AWS Services Used

| AWS Service | Purpose |
|-------------|----------|
| Amazon API Gateway | REST API endpoint |
| AWS Lambda | Serverless compute |
| Amazon DynamoDB | Data storage |
| Amazon EventBridge | Event routing |
| Amazon SQS | Message queue |
| Amazon CloudWatch | Monitoring and logs |
| AWS IAM | Permissions and security |
| AWS X-Ray | Distributed tracing |

---

# Features

- Serverless architecture
- Event-driven communication
- Asynchronous processing
- Microservices architecture
- REST API
- Structured logging
- CloudWatch monitoring
- EventBridge event routing
- DynamoDB persistence
- SQS message buffering
- Production-style AWS architecture

---

# Project Structure

```text
event-driven-order-processing/
│
├── order-service/
│   ├── lambda_function.py
│   ├── requirements.txt
│   └── README.md
│
├── payment-service/
│   ├── lambda_function.py
│   ├── requirements.txt
│   └── README.md
│
├── architecture/
│   ├── architecture-diagram.png
│   └── architecture.drawio
│
├── screenshots/
│   ├── postman-create-order.png
│   ├── api-gateway.png
│   ├── eventbridge-rule.png
│   ├── sqs-queue.png
│   ├── orders-table.png
│   ├── payments-table.png
│   ├── order-cloudwatch.png
│   └── payment-cloudwatch.png
│
├── docs/
│   ├── architecture.md
│   ├── deployment-guide.md
│   └── event-flow.md
│
├── .gitignore
├── LICENSE
└── README.md
```

---

# Event Flow

```text
Client
   │
   ▼
POST /orders
   │
   ▼
Amazon API Gateway
   │
   ▼
Order Lambda
   │
   ▼
Orders DynamoDB
   │
   ▼
OrderCreated Event
   │
   ▼
Amazon EventBridge
   │
   ▼
Amazon SQS
   │
   ▼
Payment Lambda
   │
   ▼
Payments DynamoDB
   │
   ▼
PaymentCompleted Event
   │
   ▼
Future Services
```

---

# REST API

## Create Order

### Endpoint

```http
POST /orders
```

### Request

```json
{
  "customerId": "user-1",
  "items": [
    {
      "productId": "p-1",
      "quantity": 1
    }
  ],
  "totalAmount": 19.99
}
```

### Successful Response

```json
{
  "OrderID": "2102e389-2dae-4302-b5a0-f597fce5b884",
  "CustomerID": "user-1",
  "Items": [
    {
      "productId": "p-1",
      "quantity": 1
    }
  ],
  "Status": "Pending",
  "Total": 19.99,
  "Timestamp": "2026-06-28T13:10:57Z"
}
```

---

# DynamoDB Tables

## Orders Table

| Attribute | Description |
|------------|-------------|
| OrderID | Partition Key |
| CustomerID | Customer identifier |
| Items | List of purchased products |
| Status | Pending / Confirmed / Failed |
| Total | Total order value |
| Timestamp | Order creation timestamp |

---

## Payments Table

| Attribute | Description |
|------------|-------------|
| PaymentID | Partition Key |
| OrderID | Associated order |
| CustomerID | Customer identifier |
| Amount | Payment amount |
| Status | Successful / Failed |
| Timestamp | Payment timestamp |

---

# EventBridge Events

## OrderCreated

```json
{
  "detail-type": "OrderCreated",
  "source": "orders",
  "detail": {
    "orderId": "2102e389-2dae-4302-b5a0-f597fce5b884",
    "customerId": "user-1",
    "items": [
      {
        "productId": "p-1",
        "quantity": 1
      }
    ]
  }
}
```

---

## PaymentCompleted

```json
{
  "detail-type": "PaymentCompleted",
  "source": "payments",
  "detail": {
    "paymentId": "0f721e2c-d10d-4683-ba32-42c78bda461c",
    "orderId": "2102e389-2dae-4302-b5a0-f597fce5b884",
    "status": "Successful"
  }
}
```

---

# Testing the Architecture

## Step 1 — Create an Order

Use Postman to send:

```http
POST /orders
```

with the following body:

```json
{
  "customerId": "user-1",
  "items": [
    {
      "productId": "p-1",
      "quantity": 1
    }
  ],
  "totalAmount": 19.99
}
```

Expected response:

```
200 OK
```

---

## Step 2 — Verify Orders Table

Confirm that a new order appears in the **Orders** DynamoDB table.

---

## Step 3 — Verify Order Lambda Logs

Open CloudWatch Logs and verify the following events:

- LambdaStarted
- OrderCreated
- OrderCreatedEventPublished

---

## Step 4 — Verify EventBridge

Confirm that the `OrderCreated` event is received and forwarded by EventBridge.

---

## Step 5 — Verify Amazon SQS

Ensure the EventBridge rule delivers the event to the configured SQS queue.

---

## Step 6 — Verify Payment Lambda

Open CloudWatch Logs and verify:

- LambdaStarted
- SQSMessageReceived
- PaymentProcessingStarted
- PaymentSaved
- EventPublished
- PaymentProcessingCompleted

---

## Step 7 — Verify Payments Table

Confirm that the payment record exists in the **Payments** DynamoDB table.

---

# Monitoring

Amazon CloudWatch is used for:

- Lambda logs
- Error monitoring
- Execution metrics
- Request tracing
- Performance analysis

---

# Security

- Least-privilege IAM roles
- Environment variables for configuration
- No hardcoded credentials
- Managed AWS services
- Serverless execution model

---

# Challenges Encountered

During development, the following issues were identified and resolved:

- Fixed `KeyError: customerId` caused by mismatched API request payloads.
- Resolved DynamoDB float serialization issues by converting floating-point values to `Decimal`.
- Corrected API Gateway deployment errors causing `403 Missing Authentication Token`.
- Fixed `502 Internal Server Error` responses by improving request body parsing.
- Configured EventBridge rules to correctly forward `OrderCreated` events to Amazon SQS.
- Verified successful asynchronous communication between Order Service and Payment Service.
- Added structured logging for easier CloudWatch debugging and end-to-end request tracing.

---


# Learning Outcomes

This project demonstrates practical experience with:

- Event-Driven Architecture
- AWS Lambda
- Amazon API Gateway
- Amazon EventBridge
- Amazon SQS
- Amazon DynamoDB
- Amazon CloudWatch
- IAM
- Distributed Systems
- Serverless Computing
- Structured Logging
- Microservices Communication
- Asynchronous Event Processing

---

# Author

**Chigozie Nwanze**
