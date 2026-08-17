# Awesome Foundation Core Infrastructure

> **New to this repo?** Read the [Bootstrap Guide](./BOOTSTRAP.md). It shows how to set up the infrastructure in a new AWS Organization.

This repository holds the Awesome Foundation core infrastructure components. CloudFormation templates, Docker containers, and automation scripts define the infrastructure. They keep deployments consistent across development, testing, and production environments.

## Architecture Overview

The infrastructure follows a layered approach:

1. **Foundation Layer** - VPC, networking, and security components
2. **Compute Layer** - Web applications, load balancers, and container services
3. **Access Layer** - Bastion hosts and identity management

## Infrastructure Components

### Foundation Layer

- [**awesome-vpc**](./awesome-vpc/) - Core VPC infrastructure with public and private subnets, security groups, and network ACLs
- [**awesome-cloudflare-sg**](./awesome-cloudflare-sg/) - Security group that a Lambda function and EventBridge keep in sync with the Cloudflare proxy IP ranges
- [**github_actions_oidc**](./github_actions_oidc/) - OpenID Connect integration between GitHub Actions and AWS for secure, token-based CI/CD access

### Compute Layer

- [**awesome-web**](./awesome-web/) - ECS cluster and application load balancers for web applications
- [**awesome-haproxy**](./awesome-haproxy/) - HAProxy sidecar that gives ECS services structured logging and more routing options

### Access Layer

- [**awesome-bastion**](./awesome-bastion/) - SSH bastion host for secure access to database resources
- [**aws_sso**](./aws_sso/) - AWS SSO implementation for identity management and permission sets

## Deployment Process

GitHub Actions workflows deploy most components. The usual flow is:

1. Commit your changes to a feature branch
2. Open a pull request. This starts the workflows that preview and validate the changes
3. Merge to the master branch. This starts the deployment workflows for each environment
4. Rain deploys the CloudFormation stacks

## Environments

The infrastructure runs in three environments:

- **Dev** - Development environment
- **Test** - Testing/staging environment
- **Prod** - Production environment

CloudFormation parameters, mappings, and conditions hold the settings for each environment.

## Availability Zone Configuration

Each environment can use one, two, or three Availability Zones. Environment variables in the GitHub Actions workflows set the count.

### Configuration

Three environment variables at the top of each workflow file control the Availability Zones:

```yaml
env:
  DEPLOY_AZ_ONE: 1    # 1=deploy, 0=skip
  DEPLOY_AZ_TWO: 1
  DEPLOY_AZ_THREE: 0
```

### Stack Requirements

| Stack | Minimum AZs | Notes |
|-------|-------------|-------|
| **awesome-vpc** | 1 | One AZ is enough, and it lowers the cost in dev and test |
| **awesome-web** | 2 | The ALB needs subnets in two different AZs |

### Important: Keep Settings in Sync

The VPC and Web stacks must use the same Availability Zone settings. The Web stack imports subnet references from the VPC stack. If a subnet does not exist, the deployment fails.

**Valid configurations:**
- AZ One + AZ Two (minimum for web workloads)
- AZ One + AZ Two + AZ Three (full redundancy)

**Invalid configuration:**
- One AZ only. The VPC stack deploys, then the Web stack fails

## Why We Use a Dedicated Infrastructure Domain

This infrastructure uses a dedicated domain, for example `companyname.dev`, and not a subdomain of the production domain such as `companyname.com`. This is a deliberate decision:

**Security Isolation**
- A compromised dev/test environment cannot affect production DNS or hijack production cookies
- Wildcard certificates for `*.dev.companyname.dev` stay isolated from production
- You can turn on HSTS preload in production without disturbing development work

**Operational Independence**
- Infrastructure DNS changes cannot break the customer-facing website
- Each team can manage its own domain. Marketing owns `.com`, and engineering owns `.dev`
- Short TTLs and frequent changes in dev and test do not touch production caching

**Clear Boundaries**
- The URL tells a developer which environment they are in
- A copied URL cannot reach production by accident
- Search engines do not index dev and test content, because the domain differs, even if a `noindex` header fails

**Cookie Scope**
- Authentication cookies on `.companyname.dev` cannot leak to or from `.companyname.com`
- The browser keeps the cookies of each environment apart

The convention is: `{service}.{stage}.{infra-domain}` (e.g., `api.prod.companyname.dev`).

## Common Tasks

### Adding a New Component

1. Create a new directory for your component
2. Develop the CloudFormation template
3. Create a GitHub Actions workflow in `.github/workflows/`
4. Write a README.md that describes the component

### Updating Existing Components

1. Make changes to the CloudFormation template
2. Open a pull request, and review the changes in the preview output
3. Add the PR labels that deploy to the lower environments, and test there before you merge

## Repository Structure

```
core-infrastructure/
├── awesome-bastion/         # SSH bastion host
├── awesome-cloudflare-sg/   # Cloudflare IP security group (auto-syncing)
├── awesome-haproxy/         # HAProxy sidecar
├── awesome-vpc/             # Core VPC infrastructure
├── awesome-web/             # Web application infrastructure
├── aws_sso/                 # AWS SSO implementation
└── github_actions_oidc/     # OIDC for GitHub Actions
```

## Security Considerations

- All sensitive resources use KMS encryption
- Network resources use private subnets where they can
- IAM roles hold the minimum permissions they need
- GitHub Secrets and AWS SSM hold the secrets

## Best Practices

1. Deploy through the CI/CD pipeline, not by hand
2. Write a README.md for every component
3. Read the PR preview before you merge
4. Obey the naming conventions in this repository
5. Keep changes backward compatible

## Further Reading

- [AWS CloudFormation Documentation](https://docs.aws.amazon.com/cloudformation/)
- [AWS ECS Documentation](https://docs.aws.amazon.com/ecs/)
- [Rain CloudFormation Tool](https://github.com/aws-cloudformation/rain)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
