# GitHub Actions OIDC Integration

## Overview

The GitHub Actions OIDC (OpenID Connect) project configures secure, password-less authentication between GitHub Actions workflows and AWS environments. It eliminates the need for storing long-lived AWS credentials in GitHub secrets by using a trust relationship based on short-lived tokens and identity federation.

## What This Creates

This CloudFormation project deploys:

* **OIDC Identity Provider**
  * Configures AWS to trust the GitHub Actions OIDC provider
  * Uses GitHub's token issuer URL and thumbprints for validation
  * Enables federated authentication from GitHub workflows

* **IAM Roles**
  * Creates roles that GitHub Actions can assume through OIDC
  * Defines specific trust conditions based on GitHub repository identity
  * Grants appropriate permissions to deployed resources

* **Security Controls**
  * Limits session duration to 1 hour to reduce risk exposure
  * Uses conditional policy statements to restrict access by repository
  * Different permission models for the root account vs. other accounts

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

4. **Deployment Patterns**
   * Root account has a more restrictive setup (only specific repositories allowed)
   * Member accounts are more permissive (all organization repositories allowed)
   * StackSet deployment ensures consistent configuration across accounts

## Implementation Details

The project includes two primary CloudFormation templates:

### 1. Root Account Template (`github_actions_root.yml`)

This has to be manually deployed via Cloudformation to establish the initial trust between Github Actions and AWS.

It takes a parameter of what to grant access to, can be either a whole github org, or a single repository.

Suggested deployment only allows the current repository, not the entire github org.

### 2. Member Account Template (`github_actions.yml`)

This can be deployed automatically based on the trust established with the root one.

It extends access to the relevant subaccounts, and can be extended to the entire github org.

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
        uses: aws-actions/configure-aws-credentials@v2
        with:
          role-to-assume: arn:aws:iam::123456789012:role/awesome-gha-allow-all-role
          aws-region: eu-central-1

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

## Deployment Model

The templates are deployed using different approaches to ensure appropriate access controls:

1. **Root Account**:
   * Manual deployment to ensure tight control
   * More restrictive trust conditions
   * Only allows the core-infrastructure repository

2. **Member Accounts**:
   * Deployed via CloudFormation StackSet
   * Automatically applied to new accounts
   * More permissive conditions for broader developer access

## Related Projects

This OIDC setup is a foundational security component that enables:

* **CI/CD Pipelines**: All deployment workflows throughout the infrastructure
* **AWS SSO**: Works in conjunction with IAM Identity Center for human access
* **Infrastructure Automation**: Powers all infrastructure-as-code deployments

## References

* [GitHub Actions Documentation on AWS OIDC](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
* [AWS IAM OIDC Identity Providers](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html)
* [AWS STS AssumeRoleWithWebIdentity](https://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRoleWithWebIdentity.html)
