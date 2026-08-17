# GitHub Actions OIDC Integration

## Overview

The GitHub Actions OIDC (OpenID Connect) project sets up authentication between GitHub Actions workflows and AWS environments. It uses no password. Identity federation and short-lived tokens replace the long-lived AWS credentials that a GitHub secret would otherwise hold.

## What This Creates

This CloudFormation template (`github_actions.yml`) deploys:

* **OIDC Identity Provider**
  * Tells AWS to trust the GitHub Actions OIDC provider
  * Validates the token against the issuer URL and the thumbprints from GitHub
  * Lets a GitHub workflow authenticate through identity federation

* **IAM Role**
  * Creates a role that GitHub Actions can assume through OIDC
  * Holds trust conditions that test the identity of the GitHub repository
  * Gives administrative permissions on the deployed resources

* **Security Controls**
  * Limits a session to 1 hour, which lowers the risk
  * Uses policy conditions to limit access to one repository or one organization
  * Takes a scope of one repository, or of the full organization

## How It Works

The OIDC integration follows this process:

1. **Identity Federation Setup**
   * AWS trusts the tokens from the GitHub OIDC provider
   * The OIDC provider carries the thumbprints that AWS validates against

2. **Trust Relationship**
   * The IAM role holds conditions that test the identity of the GitHub workflow
   * A workflow can assume the role only when its subject claim matches the pattern
   * Other claims, such as the branch or the environment, can make the test stricter

3. **Workflow Authorization**
   * A GitHub Action asks the GitHub OIDC provider for a token
   * GitHub returns a signed JWT that holds the claims about the workflow
   * The workflow sends this token to AWS STS, and asks to assume the IAM role
   * AWS validates the token. If the conditions match, AWS returns temporary credentials

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

Deploy the template in two phases:

### Phase 1: Root Account (Manual)

Deploy to the root account by hand. This bootstraps the CI/CD:

1. Deploy via CloudFormation Console
2. Parameter `TrustedGithubOrgOrRepoImmutable`: `your-org@ORG_ID/core-infrastructure@REPO_ID` (specific repo only)
3. Parameter `TrustedGithubOrgOrRepo`: `your-org/core-infrastructure` (the same repo, old format)
4. This creates the first trust relationship. The core-infrastructure repo can then deploy the rest of the infrastructure

Read `ORG_ID` and `REPO_ID` with `gh api /repos/your-org/core-infrastructure --jq '.owner.id, .id'`.

### Phase 2: Member Accounts (Automated via StackSet)

After the root account holds the OIDC configuration, the `github_actions_oidc_stackset.yml` workflow does this work:

1. Creates/updates a CloudFormation StackSet
2. Deploys to all member accounts in the organization
3. Parameter `TrustedGithubOrgOrRepoImmutable`: `your-org@ORG_ID/*` (all org repos, new format)
4. Parameter `TrustedGithubOrgOrRepo`: `your-org/*` (all org repos, old format)
5. Auto-deployment enabled for new accounts

The workflow reads the organization name and ID from the `github.repository_owner` and `github.repository_owner_id` context values, so both parameters need no manual step.

The result:
* **Root account**: The core-infrastructure repository only
* **Member accounts**: Every repository in the GitHub organization

## Integration with GitHub Workflows

Add these lines to a GitHub Actions workflow:

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

OIDC gives these advantages:

* **No stored secrets**: No GitHub secret holds a long-lived access key
* **Short-lived credentials**: The credentials expire at the end of the session
* **Precise control**: A policy can test the repository, the branch, and other claims
* **Audit**: AWS CloudTrail names the assumed role behind each action
* **Less credential work**: Nobody rotates or manages a credential

## Components

* **github_actions.yml**: The CloudFormation template that creates the OIDC provider and the IAM role
* **github_actions_oidc_stackset.yml**: The GitHub Actions workflow that deploys the StackSet

## References

* [GitHub Actions Documentation on AWS OIDC](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
* [AWS IAM OIDC Identity Providers](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html)
* [AWS STS AssumeRoleWithWebIdentity](https://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRoleWithWebIdentity.html)
* [Immutable subject claims for GitHub Actions OIDC tokens](https://github.blog/changelog/2026-04-23-immutable-subject-claims-for-github-actions-oidc-tokens/) (changelog)
* [GitHub REST API for OIDC subject claim customization](https://docs.github.com/en/rest/actions/oidc)
