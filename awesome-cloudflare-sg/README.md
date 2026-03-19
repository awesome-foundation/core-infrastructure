# awesome-cloudflare-sg

Self-contained CloudFormation stack that creates and maintains a security group whose inbound rules are automatically synced with [Cloudflare's published proxy IP ranges](https://www.cloudflare.com/ips/).

Attach this security group to ALBs or other resources that should only accept traffic from Cloudflare proxies.

## What it creates

- **EC2 Security Group** — empty on creation, populated by the Lambda
- **Lambda function** (Python 3.12, no external dependencies) — fetches Cloudflare IPv4 + IPv6 ranges, diffs against current rules, applies adds/removes
- **EventBridge rule** — triggers the Lambda on a schedule (default: every 6 hours)
- **CloudFormation custom resource** — runs the Lambda immediately on deploy so the SG is populated before dependent stacks use it
- **SNS topic** — notified on every sync with a summary of changes
- **SNS email subscription** (optional) — subscribe an email for alerts

## Deploy

Requires [Rain](https://github.com/aws-cloudformation/rain) for `!Rain::Embed` directive (inlines the Python file at deploy time).

```bash
rain deploy awesome-cloudflare-sg/awesome-cloudflare-sg.yml awesome-cloudflare-sg \
  --params VpcStackName=awesome-vpc,NotificationEmail=ops@example.com
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `VpcStackName` | `awesome-vpc` | VPC stack to import `VPCId` from |
| `Ports` | `443` | Comma-separated TCP ports to allow |
| `ScheduleExpression` | `rate(6 hours)` | How often to sync |
| `NotificationEmail` | *(empty)* | Email for SNS alerts (optional) |

## Outputs

| Output | Export | Description |
|--------|--------|-------------|
| `SecurityGroupId` | `${StackName}:SecurityGroupId` | Use this on ALBs/resources |
| `SnsTopicArn` | `${StackName}:SnsTopicArn` | Subscribe additional endpoints |

## Usage in other stacks

```yaml
# Reference the security group from another CloudFormation stack:
Resources:
  MyALB:
    Type: AWS::ElasticLoadBalancingV2::LoadBalancer
    Properties:
      SecurityGroups:
        - Fn::ImportValue: awesome-cloudflare-sg:SecurityGroupId
```

## How it works

1. Lambda fetches `https://www.cloudflare.com/ips-v4` and `ips-v6` (with a custom User-Agent to avoid Cloudflare's Browser Integrity Check blocking the request)
2. Compares fetched CIDRs against current SG rules
3. Adds missing rules with `authorize_security_group_ingress` (one per CIDR for fault tolerance)
4. Removes stale rules with `revoke_security_group_ingress`
5. Each rule's description includes a timestamp: `Cloudflare (added 2026-03-19 18:30 UTC)`
6. Publishes a summary to SNS — subject line flags errors or rule limit warnings
7. Alerts if total rules exceed the default SG limit of 60

## SG rule limits

AWS default: 60 inbound rules per security group (can be raised to 200).

Cloudflare currently publishes ~15 IPv4 + ~7 IPv6 ranges:
- 1 port = ~22 rules
- 2 ports (80 + 443) = ~44 rules
- 3 ports = ~66 rules (exceeds default, needs limit increase)

## Files

| File | Purpose |
|------|---------|
| `awesome-cloudflare-sg.yml` | CloudFormation template |
| `cloudflare_sg_sync.py` | Lambda function (embedded via `!Rain::Embed` at deploy time) |

## License

Apache License 2.0
