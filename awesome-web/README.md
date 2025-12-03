# Awesome Web

## Overview

The Awesome Web project provides the essential web application hosting infrastructure built on top of the Awesome VPC.

It establishes public and private load balancers, SSL certificates, ECS clusters, and other required components to support containerized web applications in AWS.

## What This Creates

This CloudFormation template deploys:

* **Load Balancers**
  * Public-facing load balancer for internet traffic
  * Private internal load balancer for service-to-service communication
  * Automatic HTTP to HTTPS redirection for both load balancers
  * SSL certificates for all domains with DNS validation
  * S3 bucket for ALB access logs with proper bucket policies

* **Elastic Container Service (ECS) Resources**
  * Default ECS cluster with Fargate and Fargate_Spot capacity providers
  * Enhanced container insights for monitoring
  * IAM roles for ECS services and task execution

* **ALB Rule Priority Management**
  * Lambda functions that automatically assign priorities to ALB listener rules
  * Prevents rule priority conflicts when deploying multiple services
  * Intelligent priority allocation in the valid range (1-50000)

* **DNS Records**
  * Records for public load balancer (`lb-public.[stage].example.dev`)
  * Records for private load balancer (`lb-private.[stage].example.dev`)

## Relation to Other Projects

The Awesome Web stack builds on the foundation provided by Awesome VPC:

* **Depends on Awesome VPC** for its network infrastructure:
  * Uses public and private subnets from the VPC
  * Leverages security groups defined in the VPC stack
  * Integrates with the Route53 DNS zone created by the VPC stack

* **Provides Resources for Other Projects**:
  * Any containerized application in the ecosystem can use this load balancer
  * Exports various ARNs, names, and hostnames for use by other stacks
  * Services like HAProxy, Redis Cache, and other web applications use this infrastructure

## Deployment Pipeline

The project uses GitHub Actions for continuous integration and deployment:

* **Main Deployment (web_deploy.yml)**
  * Triggered by changes to the Web template or workflow files on the master branch
  * Deploys to all environments (dev, test, prod) using the aws-cloudformation/rain tool
  * Authenticates to AWS using OIDC role-based authentication

* **Pull Request Workflow (web_pull_request.yml)**
  * Creates and previews CloudFormation changesets when PRs are opened or updated
  * Generates a Markdown table showing the planned resource changes
  * Optionally deploys to dev environment when PR has the "deploy-pr" label
  * Posts deployment logs back to the PR for visibility

## Initial Deployment

The deployment process requires the Awesome VPC to be deployed first:

1. Ensure the Awesome VPC stack is successfully deployed
2. Deploy the Awesome Web stack using rain:
   ```
   rain deploy awesome-web.yml --yes
   ```

3. After deployment, the stack exports several values used by other infrastructure components

## Special Components

### ALB Rule Priority Lambda

The stack includes a Lambda function that solves the common problem of ALB rule priority conflicts:

* ALB listener rules need unique priority numbers
* The Lambda automatically allocates unused priority numbers
* Prevents deployment failures caused by priority conflicts
* The Python script (allocate_alb_rule_priority.py) is embedded directly in the CloudFormation template

## Outputs

The stack exports numerous resources used by other stacks:
* Load balancer DNS names and listener ARNs
* ECS cluster name and IAM roles
* SSL certificate ARN
* Lambda function ARNs for rule priority allocation

These exported values enable other stacks to deploy applications using this web infrastructure without having to recreate these components.
