# AWS SSO (Single Sign-On)

## Overview

The AWS SSO project manages user access to the AWS infrastructure using AWS IAM Identity Center (formerly AWS Single Sign-On).

It provides centralized user management, group-based access control, and automated user provisioning across all AWS accounts.

## What This Creates

This project includes two main components:

### 1. AWS SSO Access (CloudFormation Stack)

The `aws_sso_access.yml` CloudFormation template deploys:

* **Identity Store Groups**
  * Developers - For software engineers
  * Ops - For operations personnel

* **Permission Sets**
  * DeveloperAccess - Read-only access plus limited write permissions for common developer tasks
  * AdministratorAccess - Full administrative privileges

* **Account Assignments**
  * Maps groups to AWS accounts with appropriate permission sets
  * Covers all cloud environments (Dev, Test, Prod, Root)
  * Ensures consistent access control across the organization

### 2. User Synchronization Tool

The `sync_aws_sso_users.py` script provides:

* **User Management**
  * Reads user definitions from YAML file
  * Creates new users in AWS SSO
  * Deletes users no longer defined in the YAML
  * Updates group memberships for existing users

* **Automated Workflow**
  * GitHub Actions triggers on changes to user definitions
  * Provides dry-run capability for previewing changes
  * Automated sync on merges to master

## How It Works

The system works through two main processes:

### SSO Infrastructure Deployment

1. The CloudFormation template defines the permissions infrastructure
2. AWS IAM Identity Center groups are created to represent roles (Developers, Ops, etc.)
3. Permission sets define the precise AWS permissions for each role
4. Account assignments map groups to permission sets within each AWS account

### User Management Process

1. Users are defined in `aws_sso_users.yml` with display names and group memberships
2. When changes are made to this file, a GitHub Actions workflow runs
3. On pull requests, a dry run shows what would happen without making changes
4. When merged to master, the changes are applied to AWS Identity Center
5. Users receive email invitations to set up their AWS SSO accounts

## Deployment Pipeline

The project uses GitHub Actions for deployment and user synchronization:

### Infrastructure Deployment (aws_sso_setup.yml)

* **Triggered on:**
  * Changes to CloudFormation template or workflow file
  * PRs with the "deploy-pr" label
  * Merges to master branch

* **Actions:**
  * Authenticates to AWS using the Root account credentials
  * Deploys CloudFormation stack using Rain
  * Creates and updates groups, permission sets, and assignments

### User Synchronization (aws_sso_users.yml)

* **Triggered on:**
  * Changes to user definition YAML or sync script
  * Merges to master branch

* **Actions:**
  * On PRs: Performs dry run and posts results as PR comment
  * On master: Applies changes to AWS Identity Center
  * Creates, updates, or removes users and group memberships

## User Configuration

### Local AWS CLI Configuration

Example AWS profile configuration (`~/.aws/config`):

```
[profile awesome-dev-developer]
sso_session=awesome
sso_account_id=339712722643
sso_role_name=DeveloperAccess
region=eu-central-1

[profile awesome-prod-admin]
sso_session=awesome
sso_account_id=275159665848
sso_role_name=AdministratorAccess
region=eu-central-1

[sso-session awesome]
sso_start_url=https://awesome.awsapps.com/start/
sso_region=eu-central-1
sso_registration_scopes=sso:account:access
```

### AWS CLI Usage

```bash
# Login to SSO (opens browser for authentication)
aws sso login --profile awesome-dev-developer

# Run commands with profile
aws s3 ls --profile awesome-dev-developer

# Switch roles when needed
aws s3 ls --profile awesome-prod-admin
```

## Managing Users

To add or remove users:

1. Edit the `aws_sso_users.yml` file
2. Add or modify user entries in the format:
   ```yaml
   user@example.com:
     display_name: "Full Name"
     groups:
       - Developers
   ```
3. Create a pull request
4. Review the dry run output in the PR comment
5. Merge to master to apply changes

## Permissions Overview

* **Developers:** Read-only access to most services, with permissions for common development tasks like viewing logs, updating services, and deploying via CloudFormation
* **Ops:** Full administrative access for infrastructure management

## Enabling Billing Access for SSO Users

By default, AWS does not allow IAM users or roles (including SSO roles) to access billing information, even with AdministratorAccess. To enable billing access for SSO users:

1. Log into the **root account** using the root user credentials (not SSO)
2. Click your account name in the top-right corner of the console
3. Select **Account**
4. Scroll down to **IAM user and role access to Billing information**
5. Click **Edit** and enable the setting
6. Click **Update**

Once enabled, users with AdministratorAccess will be able to view billing dashboards and cost management features.

## Components

* **aws_sso_access.yml:** CloudFormation template defining groups, permissions, and assignments
* **sync_aws_sso_users.py:** Python script for syncing users with AWS Identity Center
* **aws_sso_users.yml:** YAML file containing user definitions
* **aws_config:** Example AWS CLI configuration for SSO profiles
