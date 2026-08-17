# Awesome Bastion

## Overview

The Awesome Bastion project gives developers an SSH bastion host. Through it they reach the private resources in the Awesome Foundation AWS environment, and databases most of all. It deploys an SSH server in a container. The shell is restricted, and it permits TCP forwarding.

## What This Creates

This CloudFormation template deploys:

* **Containerized SSH Server**
  * Built on Alpine Linux, with few packages
  * Runs in AWS Fargate. Fargate Spot lowers the cost
  * Holds strictly limited system permissions
  * Accepts SSH connections from approved GitHub users only
  * Permits TCP forwarding, for the database connections
  * Listens on port 9022, which lowers the scanning noise

* **Network Load Balancer**
  * Faces the internet, so a developer machine can reach it
  * Keeps the client IP address, which helps the security logs
  * Runs TCP health checks on port 9022
  * Drains a connection in 5 seconds

* **Security and Permissions**
  * Accepts SSH key authentication only, and refuses passwords
  * Uses security groups that permit the necessary traffic only
  * Uses an IAM role that can read the SSM parameters
  * Keeps the CloudWatch logs for 90 days

* **DNS Record**
  * A readable hostname: `bastion.[stage].example.dev`
  * You connect to a name, and you do not have to remember an IP address

## How It Works

The architecture rests on three principles:

1. **Container Security**
   * It uses a reduced Alpine Linux image
   * The SSH daemon refuses password authentication
   * A hardening script removes the tools and commands that nobody needs
   * It holds one unprivileged user, `dev`, with no password

2. **User Management**
   * The `authorized_users` file lists the GitHub username of each approved user
   * The container reads the public SSH keys from GitHub when it starts
   * To grant or remove access, edit that file and deploy again

3. **Network Design**
   * The containers run in the private subnets
   * A Network Load Balancer in the public subnets forwards the SSH traffic
   * The security groups permit traffic to the SSH port only
   * The load balancer keeps the client IP address for the access log

## Relation to Other Projects

The Awesome Bastion stack works with the other infrastructure components:

* **It needs Awesome VPC** for the network infrastructure:
  * It uses the public and private subnets
  * It uses the security groups
  * It adds a record to the Route53 DNS zone

* **It needs Awesome Web** for the ECS infrastructure:
  * It uses the ECS cluster that Awesome Web creates
  * It uses the ECS task execution role

* **It gives access to**:
  * RDS databases
  * ElastiCache Redis instances
  * Legacy systems, through SSH forwarding
  * Any other TCP service in the private subnets

## Deployment Pipeline

GitHub Actions runs the integration and deployment steps:

* **Main Deployment (bastion_deploy.yml)**
  * A change to a bastion file or to a workflow file on the master branch starts this workflow
  * It builds a Docker image and pushes it to ECR
  * It deploys to dev, test, and prod with the aws-cloudformation/rain tool
  * It authenticates to AWS with an OIDC role

* **Pull Request Workflow (bastion_pull_request.yml)**
  * It repeats the same steps, but it deploys to the dev environment only
  * You can test a change there before you merge to master

* **Shared Workflow (bastion_shared_workflow.yml)**
  * Both of the workflows above call this one
  * It builds the Docker image, pushes it to ECR, and deploys the CloudFormation stack

## Usage

### Configuration

The containers are temporary, so the host key changes at each deployment. Strict host key checking then fails. To prevent this, add these lines to your `~/.ssh/config`:

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

1. Create an SSH key with `ssh-keygen` in the Windows command prompt
2. Add your public key to the `authorized_users` file
3. Set up the DataGrip SSH tunnel:
   - Select "OpenSSH config and authentication agent"
   - SSH user: `dev`
   - SSH hostname: `bastion.dev.example.dev` or `bastion.prod.example.dev`

### Adding New Users

1. Get the GitHub username of the user
2. Add it to the `authorized_users` file
3. Commit the change and push it to master
4. The GitHub Actions workflow builds the container again and deploys it

NOTE: this replaces the container, and it closes every open SSH session.

## Components

* **Dockerfile**: Defines the container image and the SSH configuration
* **docker-entrypoint.sh**: Reads the user SSH keys from GitHub
* **authorized_users**: Lists the GitHub username of each approved user
* **harden.sh**: Hardens the container
* **ssh.config**: The SSH client configuration, to connect to the other hosts
* **awesome-bastion.yml**: The CloudFormation template for the infrastructure
