# Awesome Bastion

## Overview

The Awesome Bastion project provides a secure SSH bastion host that enables developers to access private resources within the Awesome Foundation AWS environment, primarily databases. It deploys a containerized SSH server with a highly restricted shell that allows TCP forwarding while maintaining tight security controls.

## What This Creates

This CloudFormation template deploys:

* **Containerized SSH Server**
  * Based on Alpine Linux with minimal packages
  * Runs in AWS Fargate (using Fargate Spot for cost optimization)
  * Configured with strictly limited system permissions
  * SSH access limited to authorized GitHub users
  * TCP forwarding enabled for database connections
  * Custom port (9022) to reduce scanning noise

* **Network Load Balancer**
  * Internet-facing for access from developer machines
  * Preserves client IP addresses for security
  * TCP health checks on port 9022
  * Fast connection draining (5 seconds)

* **Security and Permissions**
  * Requires SSH key authentication (no password access)
  * Security groups limited to necessary access
  * IAM role with permissions to access SSM parameters
  * CloudWatch Logs configuration with 90-day retention

* **DNS Record**
  * Friendly hostname: `bastion.[stage].example.dev`
  * Makes connection easier than remembering IP addresses

## How It Works

The architecture follows these key principles:

1. **Container Security**
   * Uses a stripped-down Alpine Linux image
   * SSH daemon configured to deny password authentication
   * Hardening script removes unnecessary tools and commands
   * Single unprivileged user (`dev`) with no password

2. **User Management**
   * Authorized users defined in the `authorized_users` file (GitHub usernames)
   * Public SSH keys fetched from GitHub at container startup
   * Access is automatically granted/revoked by updating the file and redeploying

3. **Network Design**
   * Containers run in private subnets
   * Network Load Balancer in public subnets forwards SSH traffic
   * Security groups restrict traffic to the SSH port
   * Client IP preservation for access logging

## Relation to Other Projects

The Awesome Bastion stack integrates with other infrastructure components:

* **Depends on Awesome VPC** for its network infrastructure:
  * Uses public and private subnets
  * Inherits security groups
  * Utilizes the Route53 DNS zone

* **Depends on Awesome Web** for its base ECS infrastructure:
  * Uses the ECS cluster created by Awesome Web
  * Leverages the ECS task execution role

* **Provides Access to**:
  * RDS databases
  * ElastiCache Redis instances
  * Legacy systems via SSH forwarding
  * Any other TCP-based services in private subnets

## Deployment Pipeline

The project uses GitHub Actions for continuous integration and deployment:

* **Main Deployment (bastion_deploy.yml)**
  * Triggered by changes to the bastion files or workflow files on the master branch
  * Builds and pushes a Docker image to ECR
  * Deploys to all environments (dev, test, prod) using the aws-cloudformation/rain tool
  * Authenticates to AWS using OIDC role-based authentication

* **Pull Request Workflow (bastion_pull_request.yml)**
  * Similar process but only deploys to dev environment
  * Enables testing changes before merging to master

* **Shared Workflow (bastion_shared_workflow.yml)**
  * Reusable workflow used by both main and PR pipelines
  * Handles Docker build, ECR push, and CloudFormation deployment

## Usage

### Configuration

Due to the ephemeral nature of the containers, host keys change with each deployment. To avoid SSH strict host key checking failures, add this to your `~/.ssh/config`:

```
Host bastion.*.example.dev
  User dev
  StrictHostKeyChecking no
  UserKnownHostsFile=/dev/null
```

### Connecting

Connect directly to the bastion:
```
ssh bastion.dev.example.dev
```

Connect to a database through the bastion:
```
ssh -L 5432:database.internal:5432 bastion.dev.example.dev
```

### DataGrip Configuration

For Windows users with DataGrip:

1. Create an SSH key using `ssh-keygen` in Windows command prompt
2. Add your public key to the `authorized_users` file
3. Configure DataGrip SSH tunnel:
   - Use "OpenSSH config and authentication agent"
   - SSH user: `dev`
   - SSH hostname: `bastion.dev.example.dev` or `bastion.prod.example.dev`

### Adding New Users

1. Get the user's GitHub username
2. Add it to the `authorized_users` file
3. Commit and push the change to master
4. The GitHub Actions workflow will rebuild and redeploy the container

Note that this process will terminate all active SSH sessions as the container is replaced.

## Components

* **Dockerfile**: Defines the container image with SSH configuration
* **docker-entrypoint.sh**: Fetches user SSH keys from GitHub
* **authorized_users**: List of GitHub usernames granted access
* **harden.sh**: Security hardening script for the container
* **ssh.config**: SSH client configuration for connecting to other hosts
* **awesome-bastion.yml**: CloudFormation template for infrastructure
