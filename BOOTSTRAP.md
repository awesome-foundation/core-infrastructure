# Bootstrap Guide: Setting Up a New Organization

This guide walks through the complete setup of Awesome Foundation infrastructure in a new AWS Organization.

## Prerequisites

- AWS root account with Organizations enabled
- GitHub organization with a repository for this infrastructure code
- AWS CLI installed locally
- Admin access to create GitHub organization variables/secrets

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
3. Enable all features (recommended)

### 1.2 Create Member Accounts

Create three member accounts for the stage-based deployment model:

| Account Name | Purpose | Email (example) |
|--------------|---------|-----------------|
| `awesome-dev` | Development | aws+dev@yourcompany.com |
| `awesome-test` | Testing/Staging | aws+test@yourcompany.com |
| `awesome-prod` | Production | aws+prod@yourcompany.com |

In AWS Organizations:
1. Click **Add an AWS account** → **Create an AWS account**
2. Enter account name and email
3. Repeat for each environment

Note the **Account IDs** - you'll need them later.

### 1.3 Enable CloudFormation StackSets

In the root account:
1. Go to **CloudFormation** → **StackSets**
2. If prompted, enable trusted access with AWS Organizations

---

## Phase 2: GitHub Actions OIDC Integration

### 2.1 Deploy OIDC to Root Account (Manual)

This must be done manually first to bootstrap CI/CD.

1. Log into the **root account** via AWS Console
2. Go to **CloudFormation** → **Create stack**
3. Upload `github_actions_oidc/github_actions.yml`
4. Parameters:
   - **TrustedGithubOrgOrRepo**: `your-github-org/core-infrastructure` (grant access only to this repository)
5. Stack name: `github-actions-oidc`
6. Create the stack

After creation, note the role ARN:
```
arn:aws:iam::<ROOT_ACCOUNT_ID>:role/awesome-gha-allow-all-role
```

### 2.2 Configure Root Account Secret

Before the StackSet workflow can run, you need to configure the root account role as a GitHub secret.

Go to **GitHub** → **Organization Settings** → **Secrets and variables** → **Actions** → **Secrets**

Add this **organization secret**:

| Secret Name | Value |
|-------------|-------|
| `AWESOME_AWS_DEPLOY_ROLE_ROOT` | `arn:aws:iam::<ROOT_ACCOUNT_ID>:role/awesome-gha-allow-all-role` |

### 2.3 Deploy OIDC to Member Accounts via StackSet

The StackSet deployment is automated via the `github_actions_oidc_stackset.yml` workflow.

**Trigger deployment:**
- Push any change to `github_actions_oidc/github_actions.yml` or the workflow file
- Or manually trigger the workflow via GitHub Actions

The workflow will:
1. Create/update a CloudFormation StackSet named `github-actions-oidc`
2. Deploy to all member accounts in the organization
3. Set `TrustedGithubOrgOrRepo` to `your-github-org/*` (all org repos)
4. Enable auto-deployment for any new accounts added to the organization

### 2.4 Verify OIDC Roles

After StackSet deployment completes, verify the roles exist in each member account:

```bash
# For each account, the role ARN will be:
arn:aws:iam::<DEV_ACCOUNT_ID>:role/awesome-gha-allow-all-role
arn:aws:iam::<TEST_ACCOUNT_ID>:role/awesome-gha-allow-all-role
arn:aws:iam::<PROD_ACCOUNT_ID>:role/awesome-gha-allow-all-role
```

---

## Phase 3: Configure GitHub Variables

Configure GitHub organization variables so workflows can authenticate to each account.

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

The root account secret (`AWESOME_AWS_DEPLOY_ROLE_ROOT`) should already be configured from Phase 2.2. This secret is used by SSO and StackSet workflows.

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

With CI/CD working, deploy the foundational stacks.

### 4.1 Update Domain Configuration

> **Important:** We recommend using a dedicated infrastructure domain (e.g., `companyname.dev`) rather than your production domain (`companyname.com`). See [Why We Use a Dedicated Infrastructure Domain](./README.md#why-we-use-a-dedicated-infrastructure-domain) for the rationale.

Before deploying, update the domain in the VPC template:

1. Edit `awesome-vpc/awesome-vpc.yml` - update the Route53 hosted zone domain parameter - THIS CANNOT BE CHANGED LATER

Search for `example.dev` and replace with your domain.

### 4.2 Deploy VPC Stack

The VPC stack must be deployed first as other stacks depend on it.

**Configure Availability Zones:**

Before deploying, review the AZ configuration in `.github/workflows/vpc_deploy.yml`:

```yaml
env:
  DEPLOY_AZ_ONE: 1    # 1=deploy, 0=skip
  DEPLOY_AZ_TWO: 1
  DEPLOY_AZ_THREE: 0  # Enable for 3-AZ redundancy
```

> **Note:** The VPC stack can technically run in a single AZ, but the Web stack requires at least 2 AZs due to ALB requirements. Configure at minimum `DEPLOY_AZ_ONE: 1` and `DEPLOY_AZ_TWO: 1`.

**Trigger deployment:**
- Push changes to `awesome-vpc/` on the `master` branch, OR
- Manually trigger the `vpc_deploy.yml` workflow

The workflow deploys to all three environments (dev, test, prod) in parallel.

**What gets created:**
- VPC with public/private subnets across configured AZs
- Internet Gateway and NAT Gateways (one per enabled AZ)
- Route tables and security groups
- Route53 hosted zone (`dev.yourdomain.com`, `test.yourdomain.com`, `prod.yourdomain.com`)
- DynamoDB VPC endpoint

### 4.3 Deploy Web Stack

After VPC is deployed, deploy the web infrastructure.

**Configure Availability Zones:**

The Web stack must have matching AZ settings with the VPC stack. Review `.github/workflows/web_deploy.yml`:

```yaml
env:
  DEPLOY_AZ_ONE: 1    # Must match VPC settings
  DEPLOY_AZ_TWO: 1    # Must match VPC settings
  DEPLOY_AZ_THREE: 0  # Must match VPC settings
```

> **Important:** The Web stack requires a minimum of 2 AZs because AWS Application Load Balancers must have subnets in at least 2 different Availability Zones. Attempting to deploy with only 1 AZ will fail.

**Trigger deployment:**
- Push changes to `awesome-web/` on the `master` branch, OR
- Manually trigger the `web_deploy.yml` workflow

**What gets created:**
- ECS cluster (Fargate + Fargate Spot)
- Public and private Application Load Balancers (with subnets in each enabled AZ)
- ACM SSL certificate (wildcard for `*.stage.yourdomain.com`)
- ALB listener rules priority management Lambda
- S3 bucket for ALB access logs

### 4.4 Deploy HAProxy Sidecar Image

Build and push the HAProxy sidecar image to ECR:

**Trigger deployment:**
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

SSH public keys are fetched from GitHub at container startup.

### 6.2 Deploy Bastion Stack

**Trigger deployment:**
- Push changes to `awesome-bastion/` on the `master` branch

**What gets created:**
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

**Trigger deployment:**
- Push changes to `aws_sso/aws_sso_access.yml` on the `master` branch

**What gets created:**
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

### StackSet Deployment Stuck

1. Check CloudFormation StackSet operations in root account
2. Verify Organizations trusted access is enabled
3. Check individual stack instances for errors

### VPC Stack Fails

1. Check for CIDR conflicts with existing VPCs
2. Verify you have sufficient Elastic IP quota for NAT Gateways
3. Check Route53 hosted zone doesn't already exist

### SSL Certificate Stuck in Pending

1. Verify Route53 hosted zone is authoritative for the domain
2. Check DNS validation records were created
3. If using external DNS, add the CNAME records manually

---

## Next Steps

After bootstrap:

1. Set up application repositories with deployment workflows
2. Configure monitoring and alerting (CloudWatch, Datadog, etc.)
3. Set up database infrastructure (RDS, ElastiCache)
4. Configure secrets management (SSM Parameter Store, Secrets Manager)
5. Implement backup and disaster recovery procedures
