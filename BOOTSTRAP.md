# Bootstrap Guide: Setting Up a New Organization

This guide shows how to set up the Awesome Foundation infrastructure in a new AWS Organization.

## Prerequisites

- AWS root account with Organizations enabled
- GitHub organization with a repository for this infrastructure code
- AWS CLI installed locally
- Administrator access, to create the GitHub organization variables and secrets

## Overview

The setup follows this order:

1. **AWS Organization Setup** - Root account + stage-based member accounts
2. **GitHub Actions OIDC** - Deploy to root, then StackSet to member accounts
3. **GitHub Variables** - Configure role ARNs for CI/CD
4. **Core Infrastructure** - VPC and Web stacks
5. **Optional: Bastion** - For database/private subnet access
6. **Optional: SSO** - For human access via AWS IAM Identity Center

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AWS Organization                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │    Root     │  │     Dev     │  │    Test     │  │    Prod     │ │
│  │   Account   │  │   Account   │  │   Account   │  │   Account   │ │
│  │             │  │  10.8.0.0   │  │  10.9.0.0   │  │  10.10.0.0  │ │
│  │  - SSO      │  │  /16 CIDR   │  │  /16 CIDR   │  │  /16 CIDR   │ │
│  │  - StackSet │  │             │  │             │  │             │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: AWS Organization Setup

### 1.1 Create AWS Organization

1. Log into your root AWS account
2. Go to **AWS Organizations** → **Create Organization**
3. Enable all features. This is the recommended setting

### 1.2 Create Member Accounts

Create three member accounts, one for each stage:

| Account Name | Purpose | Email (example) |
|--------------|---------|-----------------|
| `awesome-dev` | Development | aws+dev@yourcompany.com |
| `awesome-test` | Testing/Staging | aws+test@yourcompany.com |
| `awesome-prod` | Production | aws+prod@yourcompany.com |

In AWS Organizations:
1. Click **Add an AWS account** → **Create an AWS account**
2. Enter the account name and the email address
3. Do this again for each environment

Write down the **Account IDs**. You need them later.

### 1.3 Enable CloudFormation StackSets

In the root account:
1. Go to **CloudFormation** → **StackSets**
2. Enable trusted access with AWS Organizations, if the console asks for it

---

## Phase 2: GitHub Actions OIDC Integration

### 2.1 Deploy OIDC to Root Account (Manual)

Do this step by hand first. It bootstraps the CI/CD.

GitHub issues OIDC tokens in a new format that carries permanent numeric IDs. This applies to every repository created, renamed, or transferred on or after July 15, 2026. The template takes one parameter per format, and it trusts every parameter that you set. Set both. See [github_actions_oidc/README.md](./github_actions_oidc/README.md#immutable-subject-claims).

Read the two numeric IDs first:

```bash
gh api /repos/your-github-org/core-infrastructure --jq '.owner.id, .id'
```

1. Log into the **root account** via AWS Console
2. Go to **CloudFormation** → **Create stack**
3. Upload `github_actions_oidc/github_actions.yml`
4. Parameters:
   - **TrustedGithubOrgOrRepoImmutable**: `your-github-org@ORG_ID/core-infrastructure@REPO_ID` (new format, grant access only to this repository)
   - **TrustedGithubOrgOrRepo**: `your-github-org/core-infrastructure` (old format, the same repository)
5. Stack name: `github-actions-oidc`
6. Create the stack

After creation, note the role ARN:
```
arn:aws:iam::<ROOT_ACCOUNT_ID>:role/awesome-gha-allow-all-role
```

### 2.2 Configure Root Account Secret

Add the root account role as a GitHub secret before you run the StackSet workflow.

Go to **GitHub** → **Organization Settings** → **Secrets and variables** → **Actions** → **Secrets**

Add this **organization secret**:

| Secret Name | Value |
|-------------|-------|
| `AWESOME_AWS_DEPLOY_ROLE_ROOT` | `arn:aws:iam::<ROOT_ACCOUNT_ID>:role/awesome-gha-allow-all-role` |

### 2.3 Deploy OIDC to Member Accounts via StackSet

The `github_actions_oidc_stackset.yml` workflow deploys the StackSet.

**To start the deployment:**
- Push a change to `github_actions_oidc/github_actions.yml` or to the workflow file
- Or start the workflow by hand from GitHub Actions

The workflow does this work:
1. Create/update a CloudFormation StackSet named `github-actions-oidc`
2. Deploy to all member accounts in the organization
3. Set `TrustedGithubOrgOrRepoImmutable` to `your-github-org@ORG_ID/*` (all org repos, new format)
4. Set `TrustedGithubOrgOrRepo` to `your-github-org/*` (all org repos, old format)
5. Enable auto-deployment for any new accounts added to the organization

Steps 3 and 4 need no manual input. The workflow reads the organization name and ID from the `github.repository_owner` and `github.repository_owner_id` context values.

### 2.4 Verify OIDC Roles

After the StackSet deployment finishes, make sure that the role exists in each member account:

```bash
# For each account, the role ARN will be:
arn:aws:iam::<DEV_ACCOUNT_ID>:role/awesome-gha-allow-all-role
arn:aws:iam::<TEST_ACCOUNT_ID>:role/awesome-gha-allow-all-role
arn:aws:iam::<PROD_ACCOUNT_ID>:role/awesome-gha-allow-all-role
```

---

## Phase 3: Configure GitHub Variables

Add the GitHub organization variables. The workflows need them to authenticate to each account.

### 3.1 Add Organization Variables

Go to **GitHub** → **Organization Settings** → **Secrets and variables** → **Actions** → **Variables**

Add these **organization variables**:

| Variable Name | Value |
|---------------|-------|
| `AWESOME_AWS_DEFAULT_REGION` | `eu-central-1` (or your preferred AWS region) |
| `AWESOME_AWS_DEPLOY_ROLE_DEV` | `arn:aws:iam::<DEV_ACCOUNT_ID>:role/awesome-gha-allow-all-role` |
| `AWESOME_AWS_DEPLOY_ROLE_TEST` | `arn:aws:iam::<TEST_ACCOUNT_ID>:role/awesome-gha-allow-all-role` |
| `AWESOME_AWS_DEPLOY_ROLE_PROD` | `arn:aws:iam::<PROD_ACCOUNT_ID>:role/awesome-gha-allow-all-role` |

> **Important:** `AWESOME_AWS_DEFAULT_REGION` must be set before running any workflows. All workflows use this variable to determine which AWS region to deploy to.

### 3.2 Verify Root Account Secret

You added the root account secret, `AWESOME_AWS_DEPLOY_ROLE_ROOT`, in Phase 2.2. The SSO and StackSet workflows use it.

### 3.3 Verify GitHub Actions Access

Create a test workflow or manually trigger a workflow to verify access works:

```yaml
# .github/workflows/test_aws_access.yml
name: Test AWS Access

on: workflow_dispatch

permissions:
  id-token: write
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        include:
          - env: dev
            role: ${{ vars.AWESOME_AWS_DEPLOY_ROLE_DEV }}
          - env: test
            role: ${{ vars.AWESOME_AWS_DEPLOY_ROLE_TEST }}
          - env: prod
            role: ${{ vars.AWESOME_AWS_DEPLOY_ROLE_PROD }}
    steps:
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ matrix.role }}
          aws-region: ${{ vars.AWESOME_AWS_DEFAULT_REGION }}

      - name: Test access
        run: |
          echo "Testing ${{ matrix.env }} account"
          aws sts get-caller-identity
```

---

## Phase 4: Deploy Core Infrastructure

The CI/CD now works. Deploy the foundation stacks.

### 4.1 Update Domain Configuration

> **Important:** Use a dedicated infrastructure domain such as `companyname.dev`, and not your production domain `companyname.com`. [Why We Use a Dedicated Infrastructure Domain](./README.md#why-we-use-a-dedicated-infrastructure-domain) gives the reasons.

Set the domain in the VPC template before you deploy.

WARNING: you cannot change the Route53 hosted zone domain after the deployment. Set the correct value now.

1. Edit `awesome-vpc/awesome-vpc.yml` and set the Route53 hosted zone domain parameter
2. Find `example.dev` and replace it with your domain

### 4.2 Deploy VPC Stack

Deploy the VPC stack first. The other stacks need it.

**Set the Availability Zones:**

Read the Availability Zone settings in `.github/workflows/vpc_deploy.yml` before you deploy:

```yaml
env:
  DEPLOY_AZ_ONE: 1    # 1=deploy, 0=skip
  DEPLOY_AZ_TWO: 1
  DEPLOY_AZ_THREE: 0  # Enable for 3-AZ redundancy
```

> **Note:** The VPC stack can run in one Availability Zone. The Web stack needs two, because the ALB needs two. Set `DEPLOY_AZ_ONE: 1` and `DEPLOY_AZ_TWO: 1` as the minimum.

**To start the deployment:**
- Push changes to `awesome-vpc/` on the `master` branch, or
- Or start the `vpc_deploy.yml` workflow by hand

The workflow deploys to dev, test, and prod at the same time.

**The workflow creates:**
- VPC with public/private subnets across configured AZs
- Internet Gateway and NAT Gateways (one per enabled AZ)
- Route tables and security groups
- Route53 hosted zone (`dev.yourdomain.com`, `test.yourdomain.com`, `prod.yourdomain.com`)
- DynamoDB VPC endpoint

### 4.3 Deploy Web Stack

Deploy the web infrastructure after the VPC stack finishes.

**Configure Availability Zones:**

The Web stack must use the same Availability Zone settings as the VPC stack. Read `.github/workflows/web_deploy.yml`:

```yaml
env:
  DEPLOY_AZ_ONE: 1    # Must match VPC settings
  DEPLOY_AZ_TWO: 1    # Must match VPC settings
  DEPLOY_AZ_THREE: 0  # Must match VPC settings
```

> **Important:** The Web stack needs two Availability Zones. An AWS Application Load Balancer needs subnets in two different Availability Zones. A deployment with one Availability Zone fails.

**To start the deployment:**
- Push changes to `awesome-web/` on the `master` branch, or
- Or start the `web_deploy.yml` workflow by hand

**The workflow creates:**
- ECS cluster (Fargate + Fargate Spot)
- Public and private Application Load Balancers (with subnets in each enabled AZ)
- ACM SSL certificate (wildcard for `*.stage.yourdomain.com`)
- ALB listener rules priority management Lambda
- S3 bucket for ALB access logs

### 4.4 Deploy HAProxy Sidecar Image

Build and push the HAProxy sidecar image to ECR:

**To start the deployment:**
- Push changes to `awesome-haproxy/` on the `master` branch

This creates ECR repositories and pushes the HAProxy image to all environments.

---

## Phase 5: Deploy an Example Application

At this point, you can deploy applications to ECS. An application deployment typically needs:

1. **ECR Repository** - For Docker images
2. **ECS Task Definition** - Container configuration
3. **ECS Service** - Running tasks behind the ALB
4. **ALB Listener Rule** - Route traffic to the service

Example minimal ECS service CloudFormation snippet:

```yaml
Resources:
  TaskDefinition:
    Type: AWS::ECS::TaskDefinition
    Properties:
      Family: my-app
      NetworkMode: awsvpc
      RequiresCompatibilities: [FARGATE]
      Cpu: 256
      Memory: 512
      ExecutionRoleArn: !ImportValue awesome-web-ECSTaskExecutionRole
      ContainerDefinitions:
        - Name: app
          Image: !Sub ${AWS::AccountId}.dkr.ecr.${AWS::Region}.amazonaws.com/my-app:latest
          PortMappings:
            - ContainerPort: 8080

  Service:
    Type: AWS::ECS::Service
    Properties:
      Cluster: default
      TaskDefinition: !Ref TaskDefinition
      DesiredCount: 2
      LaunchType: FARGATE
      NetworkConfiguration:
        AwsvpcConfiguration:
          Subnets:
            - !ImportValue awesome-vpc-PrivateSubnet1Id
            - !ImportValue awesome-vpc-PrivateSubnet2Id
          SecurityGroups:
            - !ImportValue awesome-vpc-PermissiveSecurityGroup
      LoadBalancers:
        - ContainerName: app
          ContainerPort: 8080
          TargetGroupArn: !Ref TargetGroup
```

---

## Phase 6: Deploy Bastion (Optional)

Deploy the bastion host for SSH access to resources in private subnets (databases, internal services).

### 6.1 Configure Authorized Users

Edit `awesome-bastion/authorized_users` with GitHub usernames who should have access:

```
github_username_1
github_username_2
```

The container reads the SSH public keys from GitHub when it starts.

### 6.2 Deploy Bastion Stack

**To start the deployment:**
- Push changes to `awesome-bastion/` on the `master` branch

**The workflow creates:**
- ECS service running SSH containers
- Network Load Balancer on port 22
- DNS record: `bastion.stage.yourdomain.com`

### 6.3 Connect via Bastion

```bash
# Direct connection
ssh -p 22 bastion.dev.yourdomain.com

# Port forwarding to RDS
ssh -L 5432:my-database.cluster-xxx.eu-central-1.rds.amazonaws.com:5432 \
    bastion.dev.yourdomain.com

# Then connect locally
psql -h localhost -p 5432 -U myuser mydatabase
```

---

## Phase 7: Deploy SSO (Optional)

Set up AWS IAM Identity Center for human access to AWS accounts.

### 7.1 Enable IAM Identity Center

1. Log into the **root account**
2. Go to **IAM Identity Center** (formerly AWS SSO)
3. Click **Enable**
4. Note the **Identity Store ID** (e.g., `d-1234567890`)
5. Note the **Instance ARN** (e.g., `arn:aws:sso:::instance/ssoins-1234567890`)

### 7.1a Enable IAM Billing Access

By default, AWS does not allow IAM users or roles (including SSO roles) to access billing information. To enable billing access:

1. While still logged into the **root account** as the root user
2. Click your account name in the top-right corner of the console
3. Select **Account**
4. Scroll down to **IAM user and role access to Billing information**
5. Click **Edit** and enable the setting
6. Click **Update**

### 7.2 Update SSO Configuration

Edit `aws_sso/aws_sso_access.yml` and update the mappings:

```yaml
Mappings:
  ConfigMap:
    OrgAccount:
      AccountIdProd: '<YOUR_PROD_ACCOUNT_ID>'
      AccountIdDev: '<YOUR_DEV_ACCOUNT_ID>'
      AccountIdTest: '<YOUR_TEST_ACCOUNT_ID>'
  SSOMap:
    Instance:
      IdentityStore: '<YOUR_IDENTITY_STORE_ID>'
      IAMDirectory: '<YOUR_SSO_INSTANCE_ARN>'
```

### 7.3 Deploy SSO Stack

**To start the deployment:**
- Push changes to `aws_sso/aws_sso_access.yml` on the `master` branch

**The workflow creates:**
- SSO Groups (Developers, Ops)
- Permission Sets (DeveloperAccess, AdministratorAccess)
- Account assignments linking groups to accounts

### 7.4 Add Users

Edit `aws_sso/aws_sso_users.yml` to define users:

```yaml
users:
  - username: jane.doe
    email: jane.doe@yourcompany.com
    first_name: Jane
    last_name: Doe
    groups:
      - Developers
      - Ops

  - username: john.smith
    email: john.smith@yourcompany.com
    first_name: John
    last_name: Smith
    groups:
      - Developers
```

Push changes to trigger the user sync workflow.

### 7.5 Configure AWS CLI for SSO

Users can configure their local AWS CLI:

```ini
# ~/.aws/config
[profile dev-developer]
sso_start_url = https://your-sso-portal.awsapps.com/start
sso_region = eu-central-1
sso_account_id = <DEV_ACCOUNT_ID>
sso_role_name = DeveloperAccess
region = eu-central-1

[profile prod-admin]
sso_start_url = https://your-sso-portal.awsapps.com/start
sso_region = eu-central-1
sso_account_id = <PROD_ACCOUNT_ID>
sso_role_name = AdministratorAccess
region = eu-central-1
```

Login with:
```bash
aws sso login --profile dev-developer
```

---

## Verification Checklist

After completing the bootstrap, verify:

- [ ] GitHub Actions can assume roles in all accounts (dev, test, prod, root)
- [ ] VPC stack deployed in all environments
- [ ] Web stack deployed in all environments
- [ ] Route53 hosted zones created with correct domains
- [ ] ACM certificates validated and active
- [ ] ECS cluster visible in each account
- [ ] ALBs accessible (should return 503 with no services)
- [ ] (Optional) Bastion accessible via SSH
- [ ] (Optional) SSO users can log in and access accounts

---

## Troubleshooting

### OIDC Authentication Fails

1. Verify the OIDC provider exists in the target account
2. Check the trusted repository/org matches your GitHub org
3. Ensure the workflow has `id-token: write` permission
4. Compare the subject claim format. Run `gh api /repos/OWNER/REPO/actions/oidc/customization/sub` and read `sub_claim_prefix`. A value that contains `@` means the repository uses the immutable format. Make sure `TrustedGithubOrgOrRepoImmutable` is set on the stack in the target account. The error text is `Not authorized to perform sts:AssumeRoleWithWebIdentity`. See [github_actions_oidc/README.md](./github_actions_oidc/README.md#immutable-subject-claims)

A repository that worked last week and fails now is the common case here. A rename or a transfer moves the repository to the new format.

### StackSet Deployment Stuck

1. Check CloudFormation StackSet operations in root account
2. Make sure that trusted access with AWS Organizations is on
3. Check individual stack instances for errors

### VPC Stack Fails

1. Check for CIDR conflicts with existing VPCs
2. Verify you have sufficient Elastic IP quota for NAT Gateways
3. Make sure that the Route53 hosted zone does not exist yet

### SSL Certificate Stuck in Pending

1. Verify Route53 hosted zone is authoritative for the domain
2. Make sure that the workflow created the DNS validation records
3. If using external DNS, add the CNAME records manually

---

## Next Steps

After bootstrap:

1. Set up application repositories with deployment workflows
2. Configure monitoring and alerting (CloudWatch, Datadog, etc.)
3. Set up database infrastructure (RDS, ElastiCache)
4. Configure secrets management (SSM Parameter Store, Secrets Manager)
5. Implement backup and disaster recovery procedures
