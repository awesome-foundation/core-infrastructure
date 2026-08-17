# Awesome VPC

## Overview

The Awesome VPC project gives Awesome Foundation applications their network infrastructure. It creates an AWS Virtual Private Cloud (VPC) with network segments, routing, and security. Deploy this component first, before the other infrastructure resources.

## What This Creates

This CloudFormation template deploys:

* **VPC** - A Virtual Private Cloud with a separate IP range for each environment: dev, test, and prod
* **Network Segmentation**
  * 2 Availability Zones with public and private subnets in each
  * 4k IP addresses in each public subnet, and 16k in each private subnet
  * A route table for the public subnets, and one for the private subnets
* **Networking Resources**
  * Internet Gateway for public traffic
  * NAT Gateways for private subnet internet access
  * Route tables that hold the routes for each type of subnet
* **Security**
  * A permissive security group. Add restrictions before you use it in production
* **DNS**
  * A Route53 hosted zone for service discovery
  * DNS records for NAT gateways
* **Special Resource Access**
  * DynamoDB endpoint to avoid NAT gateway charges
  * RDS subnet group for database deployments
* **Legacy Integration**
  * VPC peering connections to legacy VPCs in production and dev environments

## Relation to Other Projects

Every other infrastructure component builds on the Awesome VPC stack:

* **Awesome Web** puts its public and private ALBs in this VPC
* **Bastion Hosts** run in the public subnets of this VPC
* **HAProxy** and the other load balancers need this network structure

## Deployment Pipeline

GitHub Actions runs the integration and deployment steps:

* **Main Deployment (vpc_deploy.yml)**
  * A change to the VPC template or to a workflow file on the master branch starts this workflow
  * It deploys to dev, test, and prod with the aws-cloudformation/rain tool
  * It authenticates to AWS with an OIDC role

* **Pull Request Workflow (vpc_pull_request.yml)**
  * It creates a CloudFormation changeset when you open or update a pull request
  * It writes a Markdown table of the planned resource changes
  * It deploys to the dev environment when the pull request carries the "deploy-pr" label
  * It posts the deployment log back to the pull request

## Initial Deployment

The first deployment needs two steps:

1. Deploy the stack with required parameters:
   ```
   rain deploy awesome-vpc.yml --yes --params Stage=dev,BaseDomainName=example.dev
   ```

2. Delegate the DNS zone to the AWS nameservers
   * The `DNSZoneServers` output of the stack lists the nameservers
   * DNS resolution and certificate validation need this delegation

## Parameters

* **Stage**: The environment (dev, test, prod)
* **BaseDomainName**: The base domain for internal networking. The default is example.dev

## Outputs

The stack exports many values for the other stacks to import:
* VPC ID, subnet IDs, security group ID
* DNS zone information
* NAT gateway public IPs
* Stage name and other configuration values
