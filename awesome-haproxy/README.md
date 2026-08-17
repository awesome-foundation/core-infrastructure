# Awesome Foundation HAProxy Sidecar

## Overview

The Awesome Foundation HAProxy sidecar is a container that runs next to a web application in an ECS Fargate service. It writes structured JSON logs for all HTTP traffic. The log format stays the same across every application, and across the pre-production environments, so monitoring, debugging, and analysis stay the same too.

## What This Does

This HAProxy-based sidecar provides:

* **Structured JSON logging** - It records the request and response data in one JSON format
* **Request tracking** - It gives each request a unique ID, which lets you trace the request across systems
* **Performance metrics** - It records the time that a request spends in each stage
* **Header capture** - It logs the HTTP headers that help you debug, such as the trace ID and the user agent
* **Proxying** - It sends the request to the application container on the same host

## Key Features

### Logging Capabilities

The sidecar writes a JSON log that holds:

* The connection counts, for the active, frontend, and backend connections
* The queue data
* The times: queue time, wait time, connect time, and response time
* The network data: client IP address and ports
* The request: method, URI, protocol, and headers
* The response: status code, size, and headers
* A unique request ID, for tracing

### Runtime Configuration

Environment variables configure the container:

* `HAPROXY_LISTEN_PORT` - The port that HAProxy listens on. Default: 8000
* `HAPROXY_APP_NAME` - The name of the application. Default: haproxy
* `HAPROXY_APP_HOST` - The host that the application runs on. Default: 127.0.0.1
* `HAPROXY_APP_PORT` - The port that the application listens on. Default: 8080
* `HAPROXY_TIMEOUT_SERVER` - The server timeout. Default: 1m
* `HAPROXY_HTTP_BUFFER_REQUEST` - Turns on HTTP request buffering, which limits a slow POST attack
* `AWESOME_DEV_DOMAIN` - The domain suffix of the dev environments. HAProxy adds noindex and nofollow headers to these. Default: example.dev

### Additional Features

* **Health check** - It answers on `/_haproxy_health_check`, for the load balancer health checks
* **Prometheus metrics** - It publishes the metrics on port 9000
* **HAProxy stats** - It publishes the HAProxy stats on port 9090
* **Generated configuration** - It builds the HAProxy configuration from a template when it starts

## How It Works

1. The container runs a modified HAProxy, built on Alpine Linux
2. At startup, the `docker-entrypoint.sh` script runs the p2 templating tool. p2 reads the environment variables and builds the HAProxy configuration from `haproxy.cfg.j2`
3. HAProxy starts, and listens on the configured port
4. HAProxy sends each request to the application container, and logs the details
5. HAProxy writes the JSON logs to stdout, and AWS CloudWatch collects them

### Deployment Model

The sidecar runs as a second container inside the ECS task of the application:

```
┌───────────────────────────────┐
│       ECS Fargate Task        │
│  ┌────────────┐ ┌───────────┐ │
│  │  HAProxy   │ │    App    │ │
│  │  Sidecar   │ │           │ │
│  │            ├─┤           │ │
│  │ Port 8000  │ │ Port 8080 │ │
│  └────────────┘ └───────────┘ │
└───────────────────────────────┘
```

* External traffic reaches the HAProxy sidecar on port 8000
* HAProxy sends the request to the application on localhost:8080
* The HAProxy logs go to CloudWatch Logs

## Relation to Other Projects

This sidecar works with:

* **Awesome Web** - The applications that run on the Awesome Web infrastructure
* **ECS applications** - Any application that runs on ECS Fargate

## Deployment Pipeline

GitHub Actions runs the integration and deployment steps:

* **Build Process (awesome_haproxy_build.yml)**
  * A change to a file in the awesome-haproxy directory, or to the workflow file, starts this workflow
  * It builds the Docker images and pushes them to ECR in dev, test, and prod
  * From a pull request, it deploys to dev and test only
  * To deploy to production from a pull request, add the "deploy-pr" label

## Using with Applications

To use this sidecar with an application:

1. Add the sidecar container to your ECS task definition:
   ```json
   {
     "name": "haproxy",
     "image": "{account-id}.dkr.ecr.eu-central-1.amazonaws.com/awesome-haproxy:latest",
     "essential": true,
     "portMappings": [
       {
         "containerPort": 8000,
         "hostPort": 8000
       }
     ],
     "environment": [
       {
         "name": "HAPROXY_APP_NAME",
         "value": "your-app-name"
       },
       {
         "name": "HAPROXY_APP_PORT",
         "value": "8080"
       }
     ],
     "logConfiguration": {
       "logDriver": "awslogs",
       "options": {
         "awslogs-group": "/app/your-app-name",
         "awslogs-region": "eu-central-1",
         "awslogs-stream-prefix": "haproxy"
       }
     }
   }
   ```

2. Set your load balancer to send the traffic to the HAProxy port, 8000
3. Make sure that your application listens on the port in `HAPROXY_APP_PORT`

## Querying Logs

CloudWatch Logs Insights reads these logs. For example:

```sql
fields @timestamp,
  request.header.host,
  response.status_code,
  request.method, request.header.host, request.uri,
  time.ta, time.tc,
  request.location.continent,
  request.location.country,
  request.location.city,
  request.header.cf_connecting_ip,
  request.header.useragent,
  request.header.referer
| sort @timestamp desc
| filter ispresent(request.method)
| sort @timestamp desc
| limit 1000
```


## Components

* **Dockerfile** - Defines the container image, built on haproxytech/haproxy-alpine:3.0
* **haproxy.cfg.j2** - The template for the HAProxy configuration, including the logging setup
* **log-format.json** - The JSON structure of the log format
* **docker-entrypoint.sh** - The script that processes the templates when the container starts
* **awesome_haproxy_build.yml** - The GitHub Actions workflow that builds the image and pushes it
