"""Sync Cloudflare IP ranges into an EC2 security group.

Fetches the current Cloudflare IPv4/IPv6 CIDR lists, compares against
the security group's existing ingress rules, and applies the delta
(add new, remove stale). Publishes a summary to SNS on every run.

Invoked by:
  - EventBridge schedule (periodic sync)
  - CloudFormation custom resource (immediate sync on stack create/update)
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

# --- Logging ---

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())

# --- AWS clients (reused across warm Lambda invocations) ---

ec2 = boto3.client("ec2")
sns = boto3.client("sns")

# --- Configuration ---

SG_ID: str = os.environ.get("SECURITY_GROUP_ID", "")
PORTS: list[int] = [int(p.strip()) for p in os.environ.get("PORTS", "443").split(",") if p.strip()]
SNS_TOPIC_ARN: str = os.environ.get("SNS_TOPIC_ARN", "")
NOTIFY_ON_NO_CHANGES: bool = os.environ.get("NOTIFY_ON_NO_CHANGES", "false") == "true"

CF_URLS = [
    "https://www.cloudflare.com/ips-v4",
    "https://www.cloudflare.com/ips-v6",
]
USER_AGENT = "CloudflareIPSync/1.0"


# --- Cloudflare IP fetching ---


def fetch_cloudflare_cidrs() -> set[str]:
    """Fetch the current set of Cloudflare CIDRs (IPv4 + IPv6)."""
    cidrs: set[str] = set()
    for url in CF_URLS:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as resp:
            for line in resp.read().decode().splitlines():
                line = line.strip()
                if line:
                    cidrs.add(line)
    logger.info("Fetched %d CIDRs from Cloudflare", len(cidrs))
    return cidrs


# --- Security group operations ---


def get_current_rules() -> set[tuple[str, int]]:
    """Return existing ingress rules as a set of (cidr, port) tuples."""
    sg = ec2.describe_security_groups(GroupIds=[SG_ID])["SecurityGroups"][0]
    rules: set[tuple[str, int]] = set()
    for perm in sg.get("IpPermissions", []):
        port = perm.get("FromPort")
        if port is None:
            continue
        for r in perm.get("IpRanges", []):
            rules.add((r["CidrIp"], port))
        for r in perm.get("Ipv6Ranges", []):
            rules.add((r["CidrIpv6"], port))
    return rules


def _is_ipv6(cidr: str) -> bool:
    return ":" in cidr


def _build_permission(cidr: str, port: int, description: str | None = None) -> dict[str, Any]:
    """Build a single IpPermission dict for a CIDR/port pair."""
    perm: dict[str, Any] = {"IpProtocol": "tcp", "FromPort": port, "ToPort": port}
    if _is_ipv6(cidr):
        entry: dict[str, str] = {"CidrIpv6": cidr}
        if description:
            entry["Description"] = description
        perm["Ipv6Ranges"] = [entry]
    else:
        entry = {"CidrIp": cidr}
        if description:
            entry["Description"] = description
        perm["IpRanges"] = [entry]
    return perm


def add_rules(to_add: set[tuple[str, int]]) -> tuple[int, list[str]]:
    """Authorize new ingress rules, one per CIDR to tolerate partial failures."""
    added = 0
    errors: list[str] = []
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    description = f"Cloudflare (added {ts})"

    for cidr, port in to_add:
        perm = _build_permission(cidr, port, description)
        try:
            ec2.authorize_security_group_ingress(GroupId=SG_ID, IpPermissions=[perm])
            added += 1
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "InvalidPermission.Duplicate":
                logger.debug("Rule already exists: %s:%d (skipping)", cidr, port)
                added += 1
            else:
                logger.error("Failed to add %s:%d: %s", cidr, port, exc)
                errors.append(f"add {cidr}:{port}: {exc}")
        except Exception as exc:
            logger.error("Failed to add %s:%d: %s", cidr, port, exc)
            errors.append(f"add {cidr}:{port}: {exc}")

    return added, errors


def remove_rules(to_remove: set[tuple[str, int]]) -> tuple[int, list[str]]:
    """Revoke stale ingress rules, one per CIDR to tolerate partial failures."""
    removed = 0
    errors: list[str] = []

    for cidr, port in to_remove:
        perm = _build_permission(cidr, port)
        try:
            ec2.revoke_security_group_ingress(GroupId=SG_ID, IpPermissions=[perm])
            removed += 1
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "InvalidPermission.NotFound":
                logger.debug("Rule already gone: %s:%d (skipping)", cidr, port)
                removed += 1
            else:
                logger.error("Failed to remove %s:%d: %s", cidr, port, exc)
                errors.append(f"remove {cidr}:{port}: {exc}")
        except Exception as exc:
            logger.error("Failed to remove %s:%d: %s", cidr, port, exc)
            errors.append(f"remove {cidr}:{port}: {exc}")

    return removed, errors


# --- SNS ---


def notify(subject: str, message: str) -> None:
    """Publish a notification to the SNS topic."""
    if not SNS_TOPIC_ARN:
        logger.warning("SNS_TOPIC_ARN not set, skipping notification")
        return
    sns.publish(TopicArn=SNS_TOPIC_ARN, Subject=subject[:100], Message=message)


# --- Sync logic ---


def sync() -> dict[str, int]:
    """Core sync: fetch desired state, diff against current, apply changes."""
    if not SG_ID:
        raise RuntimeError("SECURITY_GROUP_ID environment variable is required")

    try:
        desired_cidrs = fetch_cloudflare_cidrs()
    except Exception as exc:
        notify("Cloudflare IP sync FAILED", f"Failed to fetch Cloudflare IP ranges: {exc}")
        raise

    desired_rules = {(cidr, port) for cidr in desired_cidrs for port in PORTS}
    current_rules = get_current_rules()

    to_add = desired_rules - current_rules
    to_remove = current_rules - desired_rules

    logger.info("Delta: %d to add, %d to remove", len(to_add), len(to_remove))

    all_errors: list[str] = []
    added = removed = 0

    if to_add:
        added, errs = add_rules(to_add)
        all_errors.extend(errs)

    if to_remove:
        removed, errs = remove_rules(to_remove)
        all_errors.extend(errs)

    # Check rule count against SG limit
    total_rules = len(desired_rules)
    SG_RULE_LIMIT = 60

    # Build summary
    summary = (
        f"Cloudflare IP sync complete: "
        f"{added} added, {removed} removed, "
        f"{len(desired_cidrs)} CIDRs across {len(PORTS)} port(s). "
        f"Total rules: {total_rules}/{SG_RULE_LIMIT}."
    )
    if total_rules > SG_RULE_LIMIT:
        summary += (
            f"\n\nWARNING: Total rules ({total_rules}) exceeds the default "
            f"SG limit ({SG_RULE_LIMIT}). Some rules may have failed to apply. "
            f"Request a limit increase or reduce the number of ports."
        )
    if all_errors:
        summary += f"\nErrors ({len(all_errors)}):\n" + "\n".join(all_errors)

    subject = "Cloudflare IP sync"
    if total_rules > SG_RULE_LIMIT:
        subject += " — RULE LIMIT EXCEEDED"
    elif all_errors:
        subject += " (with errors)"
    elif added or removed:
        subject += " — rules updated"
    else:
        subject += " — no changes"

    # Always log, but only notify SNS when there are changes, errors, or opt-in
    logger.info(summary)
    if added or removed or all_errors or total_rules > SG_RULE_LIMIT or NOTIFY_ON_NO_CHANGES:
        notify(subject, summary)

    return {"added": added, "removed": removed, "errors": len(all_errors)}


# --- CloudFormation custom resource response ---


def send_cfn_response(event: dict[str, Any], status: str, reason: str = "", data: dict | None = None) -> None:
    """Send a response to CloudFormation for a custom resource request."""
    response_url = event.get("ResponseURL")
    if not response_url:
        logger.error("No ResponseURL in CFN event, cannot send response")
        return

    body = json.dumps({
        "Status": status,
        "Reason": reason[:256] if reason else "See CloudWatch logs",
        "PhysicalResourceId": SG_ID or "cloudflare-sg-sync",
        "StackId": event.get("StackId", ""),
        "RequestId": event.get("RequestId", ""),
        "LogicalResourceId": event.get("LogicalResourceId", ""),
        "Data": data or {},
    }).encode("utf-8")

    req = urllib.request.Request(response_url, data=body, method="PUT", headers={"Content-Type": ""})
    urllib.request.urlopen(req, timeout=10)


# --- Lambda handler ---


def handler(event: dict[str, Any], context: Any) -> dict[str, int] | None:
    """Lambda entry point. Handles both EventBridge and CloudFormation custom resource events."""

    # CloudFormation custom resource
    if "RequestType" in event:
        try:
            if event["RequestType"] in ("Create", "Update"):
                result = sync()
                send_cfn_response(event, "SUCCESS", data=result)
            else:
                # Delete: SG rules go away with the SG, nothing to clean up
                send_cfn_response(event, "SUCCESS")
        except Exception as exc:
            logger.exception("CFN custom resource handler failed")
            send_cfn_response(event, "FAILED", reason=str(exc))
        return None

    # EventBridge scheduled invocation
    return sync()
