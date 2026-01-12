# GitHub Actions OIDC Integration

## Overview

The GitHub Actions OIDC (OpenID Connect) project configures secure, password-less authentication between GitHub Actions workflows and AWS environments. It eliminates the need for storing long-lived AWS credentials in GitHub secrets by using a trust relationship based on short-lived tokens and identity federation.

## What This Creates

This CloudFormation template (`github_actions.yml`) deploys:

* **OIDC Identity Provider**
  * Configures AWS to trust the GitHub Actions OIDC provider
  * Uses GitHub's token issuer URL and thumbprints for validation
  * Enables federated authentication from GitHub workflows

* **IAM Role**
  * Creates a role that GitHub Actions can assume through OIDC
  * Defines trust conditions based on GitHub repository identity
  * Grants administrative permissions to deployed resources

* **Security Controls**
  * Limits session duration to 1 hour to reduce risk exposure
  * Uses conditional policy statements to restrict access by repository/organization
  * Configurable scope: single repository or entire organization

## How It Works

The OIDC integration follows this process:

1. **Identity Federation Setup**
   * AWS is configured to trust tokens from GitHub's OIDC provider
   * The OIDC provider is registered with specific thumbprints for validation

2. **Trust Relationship**
   * IAM roles include conditions that validate the GitHub workflow's identity
   * Role assumption is only allowed if the repository name matches the pattern
   * Additional context like branch or environment can be used for tighter controls

3. **Workflow Authorization**
   * When a GitHub Action runs, it requests a token from GitHub's OIDC provider
   * GitHub provides a signed JWT with claims about the workflow's identity
   * The workflow presents this token to AWS STS to assume the IAM role
   * AWS validates the token and grants temporary credentials if conditions match

## Deployment Model

The template is deployed using a two-phase approach:

### Phase 1: Root Account (Manual)

The root account deployment must be done manually to bootstrap CI/CD:

1. Deploy via CloudFormation Console
2. Parameter `TrustedGithubOrgOrRepo`: `your-org/core-infrastructure` (specific repo only)
3. This creates the initial trust that allows the core-infrastructure repo to deploy further infrastructure

### Phase 2: Member Accounts (Automated via StackSet)

Once the root account has OIDC configured, the `github_actions_oidc_stackset.yml` workflow automatically:

1. Creates/updates a CloudFormation StackSet
2. Deploys to all member accounts in the organization
3. Parameter `TrustedGithubOrgOrRepo`: `your-org/*` (all org repos)
4. Auto-deployment enabled for new accounts

This approach ensures:
* **Root account**: Restricted to only the core-infrastructure repository
* **Member accounts**: Accessible by all repositories in the GitHub organization

## Integration with GitHub Workflows

To use this in a GitHub Actions workflow:

```yaml
permissions:
  id-token: write   # Required for OIDC authentication
  contents: read    # Required to checkout the repository

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Configure AWS Credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/awesome-gha-allow-all-role
          aws-region: ${{ vars.AWESOME_AWS_DEFAULT_REGION }}

      # AWS CLI commands now use temporary credentials
      - name: Test AWS access
        run: aws sts get-caller-identity
```

## Security Benefits

This OIDC-based approach offers several advantages:

* **No Stored Secrets**: Eliminates long-lived access keys in GitHub secrets
* **Short-lived Credentials**: Temporary credentials expire after the session ends
* **Fine-grained Control**: Policies can be adjusted based on repository, branch, or other attributes
* **Auditability**: Actions performed through assumed roles are clearly attributed in AWS CloudTrail
* **Reduced Credential Management**: No need for credential rotation or management

## Components

* **github_actions.yml**: CloudFormation template for OIDC provider and IAM role
* **github_actions_oidc_stackset.yml**: GitHub Actions workflow for StackSet deployment

## References

* [GitHub Actions Documentation on AWS OIDC](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
* [AWS IAM OIDC Identity Providers](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html)
* [AWS STS AssumeRoleWithWebIdentity](https://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRoleWithWebIdentity.html)
