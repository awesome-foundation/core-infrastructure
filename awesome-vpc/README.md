# Awesome VPC

## Overview

The Awesome VPC project provides the foundational network infrastructure for Awesome Foundation applications. It establishes a secure, scalable AWS Virtual Private Cloud (VPC) environment with proper network segmentation, routing, and security. This is the first component that should be deployed before other infrastructure resources.

## What This Creates

This CloudFormation template deploys:

* **VPC** - A Virtual Private Cloud environment with properly segmented IP ranges for different environments (dev/test/prod)
* **Network Segmentation**
  * 2 Availability Zones with public and private subnets in each
  * Public subnets with 4k IPs each, private subnets with 16k IPs each
  * Proper routing tables for both public and private subnets
* **Networking Resources**
  * Internet Gateway for public traffic
  * NAT Gateways for private subnet internet access
  * Route tables with appropriate routes for each subnet type
* **Security**
  * A permissive security group (note: not recommended for production use without restriction)
* **DNS**
  * A Route53 hosted zone for service discovery
  * DNS records for NAT gateways
* **Special Resource Access**
  * DynamoDB endpoint to avoid NAT gateway charges
  * RDS subnet group for database deployments
* **Legacy Integration**
  * VPC peering connections to legacy VPCs in production and dev environments

## Relation to Other Projects

The Awesome VPC stack is the foundation for all other infrastructure components in the Awesome Foundation ecosystem:

* **Awesome Web** relies on this VPC for its public and private ALBs
* **Bastion Hosts** are deployed into the public subnets of this VPC
* **HAProxy** and other load balancers depend on this network structure

## Deployment Pipeline

The project uses GitHub Actions for continuous integration and deployment:

* **Main Deployment (vpc_deploy.yml)**
  * Triggered by changes to the VPC template or workflow files on the master branch
  * Deploys to all environments (dev, test, prod) using the aws-cloudformation/rain tool
  * Authenticates to AWS using OIDC role-based authentication

* **Pull Request Workflow (vpc_pull_request.yml)**
  * Creates and previews CloudFormation changesets when PRs are opened or updated
  * Generates a Markdown table showing the planned resource changes
  * Optionally deploys to dev environment when PR has the "deploy-pr" label
  * Posts deployment logs back to the PR for visibility

## Initial Deployment

First-time deployment requires:

1. Deploy the stack with required parameters:
   ```
   rain deploy awesome-vpc.yml --yes --params Stage=dev,BaseDomainName=example.dev
   ```

2. After initial deployment, the DNS zone must be delegated to AWS nameservers
   * The nameservers are provided in the `DNSZoneServers` output of the stack
   * This delegation is necessary for proper DNS resolution and certificate validation

## Parameters

* **Stage**: The environment (dev, test, prod)
* **BaseDomainName**: Base domain for internal networking (default: example.dev)

## Outputs

The stack exports numerous values used by other stacks:
* VPC ID, subnet IDs, security group ID
* DNS zone information
* NAT gateway public IPs
* Stage name and other configuration values
