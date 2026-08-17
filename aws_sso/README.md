# AWS SSO (Single Sign-On)

## Overview

The AWS SSO project controls user access to the AWS infrastructure through AWS IAM Identity Center, which AWS previously called AWS Single Sign-On.

It holds the users in one place, controls access by group, and creates the users in every AWS account.

## What This Creates

This project includes two main components:

### 1. AWS SSO Access (CloudFormation Stack)

The `aws_sso_access.yml` CloudFormation template deploys:

* **Identity Store Groups**
  * Developers - For software engineers
  * Ops - For operations personnel

* **Permission Sets**
  * DeveloperAccess - Read access, plus the write permissions that a developer needs for daily work
  * AdministratorAccess - Full administrative permissions

* **Account Assignments**
  * They connect each group to an AWS account through a permission set
  * They cover the Dev, Test, Prod, and Root environments
  * They keep access control the same across the organization

### 2. User Synchronization Tool

The `sync_aws_sso_users.py` script does this work:

* **User management**
  * It reads the user definitions from a YAML file
  * It creates the new users in AWS SSO
  * It deletes the users that the YAML file no longer lists
  * It updates the group membership of the current users

* **Workflow**
  * A change to the user definitions starts a GitHub Actions workflow
  * A dry run shows the changes before you apply them
  * A merge to master applies the changes

## How It Works

The system runs two processes:

### SSO Infrastructure Deployment

1. The CloudFormation template defines the permission infrastructure
2. It creates an AWS IAM Identity Center group for each role, such as Developers and Ops
3. A permission set holds the exact AWS permissions of each role
4. An account assignment connects a group to a permission set inside one AWS account

### User Management Process

1. `aws_sso_users.yml` lists each user with a display name and the groups they belong to
2. A change to this file starts a GitHub Actions workflow
3. On a pull request, a dry run shows the changes and applies nothing
4. On a merge to master, the workflow applies the changes to AWS Identity Center
5. Each user receives an email invitation to set up their AWS SSO account

## Deployment Pipeline

GitHub Actions runs the deployment and the user sync:

### Infrastructure Deployment (aws_sso_setup.yml)

* **This workflow starts on:**
  * A change to the CloudFormation template or to the workflow file
  * A pull request that carries the "deploy-pr" label
  * A merge to the master branch

* **It does this work:**
  * It authenticates to AWS with the Root account credentials
  * It deploys the CloudFormation stack with Rain
  * It creates and updates the groups, permission sets, and assignments

### User Synchronization (aws_sso_users.yml)

* **This workflow starts on:**
  * A change to the user definition YAML file or to the sync script
  * A merge to the master branch

* **It does this work:**
  * On a pull request, it runs a dry run and posts the result as a comment
  * On master, it applies the changes to AWS Identity Center
  * It creates, updates, and removes the users and their group membership

## User Configuration

### Local AWS CLI Configuration

An example AWS profile in `~/.aws/config`:

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
# Log in to SSO. This opens a browser for the authentication
aws sso login --profile awesome-dev-developer

# Run a command with a profile
aws s3 ls --profile awesome-dev-developer

# Change to a different role
aws s3 ls --profile awesome-prod-admin
```

## Managing Users

To add or remove users:

1. Edit the `aws_sso_users.yml` file
2. Add or change a user entry. Use this format:
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

* **Developers:** Read access to most services. They can also read logs, update services, and deploy through CloudFormation
* **Ops:** Full administrative access, to manage the infrastructure

## Enabling Billing Access for SSO Users

By default, AWS refuses billing information to an IAM user or role, and this includes an SSO role with AdministratorAccess. To give SSO users access to the billing information:

1. Log into the **root account** using the root user credentials (not SSO)
2. Click your account name in the top-right corner of the console
3. Select **Account**
4. Scroll down to **IAM user and role access to Billing information**
5. Click **Edit** and enable the setting
6. Click **Update**

A user with AdministratorAccess can then read the billing dashboards and the cost management pages.

## Components

* **aws_sso_access.yml:** The CloudFormation template that defines the groups, permissions, and assignments
* **sync_aws_sso_users.py:** The Python script that syncs the users with AWS Identity Center
* **aws_sso_users.yml:** The YAML file that lists the users
* **aws_config:** An example AWS CLI configuration for the SSO profiles
