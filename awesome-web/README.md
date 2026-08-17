# Awesome Web

## Overview

The Awesome Web project gives web applications their hosting infrastructure. It builds on the Awesome VPC.

It creates public and private load balancers, SSL certificates, ECS clusters, and the other components that a container-based web application needs in AWS.

## What This Creates

This CloudFormation template deploys:

* **Load Balancers**
  * A public load balancer for internet traffic
  * A private load balancer for traffic between services
  * A redirect from HTTP to HTTPS on both load balancers
  * SSL certificates for all domains, validated through DNS
  * An S3 bucket for the ALB access logs, with the necessary bucket policies

* **Elastic Container Service (ECS) Resources**
  * A default ECS cluster with the Fargate and Fargate_Spot capacity providers
  * Enhanced container insights for monitoring
  * IAM roles for the ECS services and for task execution

* **ALB Rule Priority Management**
  * Lambda functions that give each ALB listener rule a priority
  * No priority conflict when you deploy more than one service
  * Priorities allocated inside the valid range of 1 to 50000

* **DNS Records**
  * Records for the public load balancer: `lb-public.[stage].example.dev`
  * Records for the private load balancer: `lb-private.[stage].example.dev`

## Relation to Other Projects

The Awesome Web stack builds on Awesome VPC:

* **It needs Awesome VPC** for the network infrastructure:
  * It uses the public and private subnets of the VPC
  * It uses the security groups from the VPC stack
  * It adds records to the Route53 DNS zone that the VPC stack creates

* **It supplies resources to other projects**:
  * Any container-based application can use this load balancer
  * It exports ARNs, names, and hostnames for the other stacks
  * HAProxy, Redis Cache, and the other web applications use this infrastructure

## Deployment Pipeline

GitHub Actions runs the integration and deployment steps:

* **Main Deployment (web_deploy.yml)**
  * A change to the Web template or to a workflow file on the master branch starts this workflow
  * It deploys to dev, test, and prod with the aws-cloudformation/rain tool
  * It authenticates to AWS with an OIDC role

* **Pull Request Workflow (web_pull_request.yml)**
  * It creates a CloudFormation changeset when you open or update a pull request
  * It writes a Markdown table of the planned resource changes
  * It deploys to the dev environment when the pull request carries the "deploy-pr" label
  * It posts the deployment log back to the pull request

## Initial Deployment

Deploy the Awesome VPC stack first:

1. Make sure the Awesome VPC stack deployed without errors
2. Deploy the Awesome Web stack using rain:
   ```
   rain deploy awesome-web.yml --yes
   ```

3. After the deployment, the stack exports the values that the other components import

## Special Components

### ALB Rule Priority Lambda

The stack holds a Lambda function that prevents ALB rule priority conflicts:

* Each ALB listener rule needs a unique priority number
* The Lambda function allocates a priority number that no other rule uses
* A priority conflict can no longer fail the deployment
* The CloudFormation template holds the Python script, `allocate_alb_rule_priority.py`

## Outputs

The stack exports many values for the other stacks to import:
* Load balancer DNS names and listener ARNs
* ECS cluster name and IAM roles
* SSL certificate ARN
* Lambda function ARNs for rule priority allocation

The other stacks import these values and deploy their applications on this web infrastructure. They do not create these components again.
