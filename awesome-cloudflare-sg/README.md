# awesome-cloudflare-sg

A self-contained CloudFormation stack. It creates a security group and keeps the inbound rules in sync with the [Cloudflare proxy IP ranges](https://www.cloudflare.com/ips/).

Attach this security group to an ALB, or to any resource that must accept traffic from Cloudflare proxies only.

## What it creates

- **EC2 Security Group**. Empty at creation. The Lambda function fills it
- **Lambda function**. Python 3.12, no external dependencies. It reads the Cloudflare IPv4 and IPv6 ranges, compares them with the current rules, then adds and removes rules
- **EventBridge rule**. It starts the Lambda function on a schedule. The default is every 6 hours
- **CloudFormation custom resource**. It runs the Lambda function during the deployment, so the security group holds rules before another stack uses it
- **SNS topic**. It receives a summary of the changes after each sync
- **SNS email subscription**. Optional. Add an email address to receive the alerts

## Deploy

This stack needs [Rain](https://github.com/aws-cloudformation/rain) for the `!Rain::Embed` directive. Rain puts the Python file into the template during the deployment.

```bash
rain deploy awesome-cloudflare-sg/awesome-cloudflare-sg.yml awesome-cloudflare-sg \
  --params VpcStackName=awesome-vpc,NotificationEmail=ops@example.com
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `VpcStackName` | `awesome-vpc` | The VPC stack that exports `VPCId` |
| `Ports` | `443` | The TCP ports to allow, separated by commas |
| `ScheduleExpression` | `rate(6 hours)` | The interval between syncs |
| `NotificationEmail` | *(empty)* | Optional. The email address for the SNS alerts |

## Outputs

| Output | Export | Description |
|--------|--------|-------------|
| `SecurityGroupId` | `${StackName}:SecurityGroupId` | Attach this to an ALB or another resource |
| `SnsTopicArn` | `${StackName}:SnsTopicArn` | Add more subscribers to this topic |

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

1. The Lambda function reads `https://www.cloudflare.com/ips-v4` and `ips-v6`. It sends a custom User-Agent, because the Cloudflare Browser Integrity Check blocks the default one
2. It compares the CIDR ranges with the current security group rules
3. It adds the missing rules with `authorize_security_group_ingress`. One call per CIDR limits the effect of a failure
4. It removes the old rules with `revoke_security_group_ingress`
5. It writes a timestamp into the description of each rule: `Cloudflare (added 2026-03-19 18:30 UTC)`
6. It publishes a summary to SNS. The subject line shows errors and rule limit warnings
7. It sends an alert when the rule count goes above the default limit of 60

## SG rule limits

AWS allows 60 inbound rules for each security group by default. You can request an increase to 200.

Cloudflare publishes approximately 15 IPv4 ranges and 7 IPv6 ranges:

- 1 port gives approximately 22 rules
- 2 ports, 80 and 443, give approximately 44 rules
- 3 ports give approximately 66 rules. This is more than the default, so you must request an increase

## Files

| File | Purpose |
|------|---------|
| `awesome-cloudflare-sg.yml` | CloudFormation template |
| `cloudflare_sg_sync.py` | The Lambda function. `!Rain::Embed` puts it into the template during the deployment |

## License

Apache License 2.0
