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

## Immutable Subject Claims

GitHub changed the format of the `sub` claim in Actions OIDC tokens. A trust policy that matches only the old format will reject the token.

### What changed

Old format:

```
repo:my-org/my-repo:ref:refs/heads/main
```

New format:

```
repo:my-org@144436715/my-repo@1109355301:ref:refs/heads/main
```

The number after each `@` is the permanent numeric ID of the owner and of the repository. GitHub assigns these IDs when you create the resource. A rename or a transfer does not change them.

### Why GitHub made this change

The old format used names only. A name becomes free when you release it, and another account can then claim it. If you deleted or renamed a repository, that account could take the old name and mint tokens with the same `sub` claim. That account could then assume your IAM role. Numeric IDs are unique and permanent, so this attack no longer works.

### Which repositories use which format

| Repository | Format |
|---|---|
| Created before July 15, 2026 | Old, until you opt in |
| Created on or after July 15, 2026 | New, always |
| Renamed or transferred on or after July 15, 2026 | New, always |

Read the third row carefully. A rename or a transfer moves a repository to the new format even if you created it years earlier. This is the case that surprises people, because the repository worked yesterday.

### How this template handles both formats

`github_actions.yml` takes one parameter per format and trusts every parameter that you set:

| Parameter | Format | Example |
|---|---|---|
| `TrustedGithubOrgOrRepoImmutable` | New, with numeric IDs | `your-org@144436715/*` |
| `TrustedGithubOrgOrRepo` | Old, names only | `your-org/*` |

Both parameters default to an empty string, and an empty parameter adds no pattern. Set the immutable parameter for all new work. Keep the legacy parameter until every repository uses the new format, then clear it.

The template builds the `sub` condition from the parameters that hold a value:

```yaml
StringLike:
  token.actions.githubusercontent.com:sub:
    - !If [TrustImmutableSubject, !Sub 'repo:${TrustedGithubOrgOrRepoImmutable}:*', !Ref "AWS::NoValue"]
    - !If [TrustLegacySubject, !Sub 'repo:${TrustedGithubOrgOrRepo}:*', !Ref "AWS::NoValue"]
```

IAM applies OR across the values, so a token that matches either pattern can assume the role.

If you leave both parameters empty, the list is empty and CloudFormation refuses to create the stack. This is deliberate. An empty list fails at deployment time, which is easier to diagnose than a role that nobody can assume.

### What happens if you trust only the old format

A token in the new format starts with `repo:your-org@144436715/`. The pattern `repo:your-org/*:*` needs the literal text `repo:your-org/`, so the two do not match. AWS STS then returns:

```
Not authorized to perform sts:AssumeRoleWithWebIdentity
```

The error names no claim and no value, so the cause is not obvious. Set `TrustedGithubOrgOrRepoImmutable` to prevent this.

### How to read the format of a repository

```bash
gh api /repos/OWNER/REPO/actions/oidc/customization/sub
```

The response gives the exact prefix that your trust policy has to match:

```json
{
  "use_default": true,
  "use_immutable_subject": false,
  "sub_claim_prefix": "repo:your-org/your-repo"
}
```

Treat `sub_claim_prefix` as authoritative and copy it into the trust policy. Do not assemble the prefix by hand.

### How to set the parameters

Read your organization ID with:

```bash
gh api /orgs/YOUR-ORG --jq '.id'
```

For an organization-wide role, set both parameters:

```
TrustedGithubOrgOrRepoImmutable = your-org@144436715/*
TrustedGithubOrgOrRepo          = your-org/*
```

For a role that trusts one repository, add the repository ID:

```
TrustedGithubOrgOrRepoImmutable = your-org@144436715/core-infrastructure@1109355301
TrustedGithubOrgOrRepo          = your-org/core-infrastructure
```

The StackSet workflow sets both parameters for you. It reads the organization name and ID from the `github.repository_owner` and `github.repository_owner_id` context values, so member accounts need no manual step.

Clear `TrustedGithubOrgOrRepo` after every repository in the organization uses the new format.

### Do not put a wildcard on the numeric ID

This value looks convenient and it is not safe:

```
# WRONG. Do not use this.
TrustedGithubOrgOrRepoImmutable = your-org*/*
```

The text `your-org*` also matches `your-org-attacker`. Anyone can create that organization on GitHub and assume your role. Write the numeric ID in full.

### How to opt in early

Move one repository to the new format:

```bash
gh api -X PUT /repos/OWNER/REPO/actions/oidc/customization/sub \
  -F use_default=true -F use_immutable_subject=true
```

An organization-wide switch exists in organization settings, and on the `PUT /orgs/{org}/actions/oidc/customization/sub` endpoint.

Set `TrustedGithubOrgOrRepoImmutable` and deploy the stack before you opt in. A repository that switches format ahead of its trust policy loses AWS access on the next workflow run.

## Deployment Model

Read [Immutable Subject Claims](#immutable-subject-claims) before you set the trust parameters.

The template is deployed using a two-phase approach:

### Phase 1: Root Account (Manual)

The root account deployment must be done manually to bootstrap CI/CD:

1. Deploy via CloudFormation Console
2. Parameter `TrustedGithubOrgOrRepoImmutable`: `your-org@ORG_ID/core-infrastructure@REPO_ID` (specific repo only)
3. Parameter `TrustedGithubOrgOrRepo`: `your-org/core-infrastructure` (the same repo, old format)
4. This creates the initial trust that allows the core-infrastructure repo to deploy further infrastructure

Read `ORG_ID` and `REPO_ID` with `gh api /repos/your-org/core-infrastructure --jq '.owner.id, .id'`.

### Phase 2: Member Accounts (Automated via StackSet)

Once the root account has OIDC configured, the `github_actions_oidc_stackset.yml` workflow automatically:

1. Creates/updates a CloudFormation StackSet
2. Deploys to all member accounts in the organization
3. Parameter `TrustedGithubOrgOrRepoImmutable`: `your-org@ORG_ID/*` (all org repos, new format)
4. Parameter `TrustedGithubOrgOrRepo`: `your-org/*` (all org repos, old format)
5. Auto-deployment enabled for new accounts

The workflow reads the organization name and ID from the `github.repository_owner` and `github.repository_owner_id` context values, so both parameters need no manual step.

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
* [Immutable subject claims for GitHub Actions OIDC tokens](https://github.blog/changelog/2026-04-23-immutable-subject-claims-for-github-actions-oidc-tokens/) (changelog)
* [GitHub REST API for OIDC subject claim customization](https://docs.github.com/en/rest/actions/oidc)
