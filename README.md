# Awesome Foundation Core Infrastructure

> **New to this repo?** See the [Bootstrap Guide](./BOOTSTRAP.md) for setting up infrastructure in a new AWS Organization.

This repository contains the Awesome Foundation core infrastructure components. The infrastructure is defined using CloudFormation templates, Docker containers, and automation scripts to ensure consistent deployments across development, testing, and production environments.

## Architecture Overview

The infrastructure follows a layered approach:

1. **Foundation Layer** - VPC, networking, and security components
2. **Compute Layer** - Web applications, load balancers, and container services
3. **Access Layer** - Bastion hosts and identity management

## Infrastructure Components

### Foundation Layer

- [**awesome-vpc**](./awesome-vpc/) - Core VPC infrastructure with public and private subnets, security groups, and network ACLs
- [**github_actions_oidc**](./github_actions_oidc/) - OpenID Connect integration between GitHub Actions and AWS for secure, token-based CI/CD access

### Compute Layer

- [**awesome-web**](./awesome-web/) - ECS cluster and application load balancers for web applications
- [**awesome-haproxy**](./awesome-haproxy/) - HAProxy sidecar for ECS services providing structured logging and advanced routing

### Access Layer

- [**awesome-bastion**](./awesome-bastion/) - SSH bastion host for secure access to database resources
- [**aws_sso**](./aws_sso/) - AWS SSO implementation for identity management and permission sets

## Deployment Process

Most components are deployed automatically via GitHub Actions workflows. The typical deployment flow is:

1. Changes are committed to a feature branch
2. A pull request is created, which triggers workflow runs for preview/validation
3. Merging to the master branch triggers deployment workflows across environments
4. CloudFormation stacks are deployed using the Rain tool

## Environments

The infrastructure is deployed across three environments:

- **Dev** - Development environment
- **Test** - Testing/staging environment
- **Prod** - Production environment

Environment-specific configurations are managed through CloudFormation parameters, mappings, and condition statements.

## Why We Use a Dedicated Infrastructure Domain

This infrastructure uses a dedicated domain (e.g., `companyname.dev`) rather than subdomains of the production domain (e.g., `companyname.com`). This is an intentional architectural decision:

**Security Isolation**
- A compromised dev/test environment cannot affect production DNS or hijack production cookies
- Wildcard certificates for `*.dev.companyname.dev` are completely isolated from production
- HSTS preload can be enabled on production without affecting development workflows

**Operational Independence**
- Infrastructure DNS changes don't risk breaking the customer-facing website
- Different teams can manage each domain independently (marketing owns `.com`, engineering owns `.dev`)
- Aggressive TTLs and frequent changes in dev/test won't impact production caching

**Clear Boundaries**
- Developers immediately know which environment they're working with from the URL
- Prevents accidental production access when copy-pasting URLs
- Search engines won't index dev/test content even if `noindex` headers fail (different domain entirely)

**Cookie Scope**
- Authentication cookies on `.companyname.dev` cannot leak to or from `.companyname.com`
- Each environment's cookies are naturally isolated

The convention is: `{service}.{stage}.{infra-domain}` (e.g., `api.prod.companyname.dev`).

## Common Tasks

### Adding a New Component

1. Create a new directory for your component
2. Develop the CloudFormation template
3. Create a GitHub Actions workflow in `.github/workflows/`
4. Document the component with a thorough README.md

### Updating Existing Components

1. Make changes to the CloudFormation template
2. Submit a PR to review changes via the preview capability
3. Use appropriate PR labels to test deployments in lower environments before merging

## Repository Structure

```
core-infrastructure/
├── awesome-bastion/         # SSH bastion host
├── awesome-haproxy/         # HAProxy sidecar
├── awesome-vpc/             # Core VPC infrastructure
├── awesome-web/             # Web application infrastructure
├── aws_sso/                 # AWS SSO implementation
└── github_actions_oidc/     # OIDC for GitHub Actions
```

## Security Considerations

- All sensitive resources use KMS encryption
- Network resources use private subnets where appropriate
- IAM roles follow least-privilege principles
- Secrets are managed through GitHub Secrets and AWS SSM

## Best Practices

1. Always use the CI/CD pipeline rather than manual deployments
2. Document all components thoroughly
3. Use PR previews to validate changes before merging
4. Follow the established naming conventions
5. Ensure backward compatibility when making changes

## Further Reading

- [AWS CloudFormation Documentation](https://docs.aws.amazon.com/cloudformation/)
- [AWS ECS Documentation](https://docs.aws.amazon.com/ecs/)
- [Rain CloudFormation Tool](https://github.com/aws-cloudformation/rain)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
