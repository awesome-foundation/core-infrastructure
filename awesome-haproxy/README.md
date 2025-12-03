# Awesome Foundation HAProxy Sidecar

## Overview

The Awesome Foundation HAProxy sidecar is a specialized container designed to run alongside web applications in ECS Fargate services. Its primary purpose is to produce standardized, structured JSON logs for all HTTP traffic, allowing for consistent monitoring, debugging, and analytics across all applications, including pre-production environments.

## What This Does

This HAProxy-based sidecar provides:

* **Structured JSON Logging** - Captures detailed request and response data in a standardized JSON format
* **Request Tracking** - Assigns unique IDs to each request for tracing across systems
* **Performance Metrics** - Records timing data for requests through various stages of processing
* **Header Capture** - Logs important HTTP headers for debugging, including trace IDs and user agents
* **Simple Proxying** - Routes requests to the application container on the same host

## Key Features

### Logging Capabilities

The sidecar generates comprehensive JSON logs that include:

* Connection details (active connections, frontend/backend connections)
* Queue information
* Detailed timing metrics (request queue time, wait time, connect time, response time)
* Network information (client IP, ports)
* Full request details (method, URI, protocol, headers)
* Response data (status code, size, headers)
* Unique request IDs for tracing

### Runtime Configuration

The container supports configuration through environment variables:

* `HAPROXY_LISTEN_PORT` - Port on which HAProxy listens (default: 8000)
* `HAPROXY_APP_NAME` - Name of the application (default: haproxy)
* `HAPROXY_APP_HOST` - Host where the application runs (default: 127.0.0.1)
* `HAPROXY_APP_PORT` - Port on which the application listens (default: 8080)
* `HAPROXY_TIMEOUT_SERVER` - Server timeout (default: 1m)
* `HAPROXY_HTTP_BUFFER_REQUEST` - Enable HTTP request buffering for slow POST attack mitigation
* `AWESOME_DEV_DOMAIN` - Domain suffix for dev environments that should have noindex/nofollow headers (default: example.dev)

### Additional Features

* **Health Check** - Provides `/_haproxy_health_check` endpoint for load balancer health checks
* **Prometheus Metrics** - Exposes metrics on port 9000 for monitoring
* **HAProxy Stats** - Provides HAProxy stats on port 9090
* **Auto-generated Config** - Uses templating at runtime to generate the HAProxy configuration

## How It Works

1. The container runs a modified version of HAProxy based on Alpine Linux
2. At startup, the `docker-entrypoint.sh` script uses the p2 templating tool to generate the HAProxy configuration from `haproxy.cfg.j2` using environment variables
3. HAProxy starts and listens on the configured port
4. All requests are forwarded to the application container while capturing detailed logs
5. Logs are written to stdout in JSON format, which is captured by AWS CloudWatch

### Deployment Model

The sidecar is deployed as a second container in the same ECS task as the application:

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
* HAProxy forwards requests to the application on localhost:8080
* Logs from HAProxy flow to CloudWatch Logs

## Relation to Other Projects

This sidecar is closely related to:

* **Awesome Web** - Works with applications deployed through the Awesome Web infrastructure
* **ECS Applications** - Designed to run alongside any ECS Fargate-based application

## Deployment Pipeline

The project uses GitHub Actions for continuous integration and deployment:

* **Build Process (awesome_haproxy_build.yml)**
  * Triggered by changes to files in the awesome-haproxy directory or workflow file
  * Builds and pushes Docker images to ECR in all environments (dev, test, prod)
  * For pull requests, only deploys to dev and test by default
  * Requires the "deploy-pr" label to deploy to production during PR

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

2. Configure your load balancer to route traffic to the HAProxy port (8000)
3. Ensure your application listens on the port specified in `HAPROXY_APP_PORT`

## Querying Logs

The logs can be queried using CloudWatch Logs Insights, for example:

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

* **Dockerfile** - Defines the container image based on haproxytech/haproxy-alpine:3.0
* **haproxy.cfg.j2** - Template for HAProxy configuration with advanced logging setup
* **log-format.json** - JSON structure defining the log format
* **docker-entrypoint.sh** - Script that runs at container startup to process templates
* **awesome_haproxy_build.yml** - GitHub Actions workflow for building and pushing the image
