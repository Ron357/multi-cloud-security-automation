#!/usr/bin/env python3
"""
mfa_compliance_report.py

Cross-cloud MFA compliance auditor.

Walks the AWS IAM user directory (via boto3) and the Microsoft Entra ID
directory (via the Microsoft Graph API), checks whether each identity has
at least one MFA method registered, and writes a single combined CSV
report so both clouds can be reviewed side by side.

Nothing in this script is hardcoded to a specific account, tenant, or
region -- everything comes from environment variables or CLI flags, so it
can be pointed at any environment without editing code.

Required environment variables
-------------------------------
AWS side (standard boto3 credential resolution -- profile, env vars, or an
assumed role all work; nothing AWS-specific needs to be set here beyond
what boto3 already expects):
    AWS_PROFILE / AWS_ACCESS_KEY_ID+AWS_SECRET_ACCESS_KEY   (either)
    AWS_REGION                                              (optional, default us-east-1)

Azure / Entra ID side (an app registration with
UserAuthenticationMethod.Read.All and User.Read.All application
permissions, admin-consented):
    AZURE_TENANT_ID
    AZURE_CLIENT_ID
    AZURE_CLIENT_SECRET

Usage
-----
    python3 mfa_compliance_report.py --aws --azure --output mfa_report.csv
    python3 mfa_compliance_report.py --aws-only
    python3 mfa_compliance_report.py --azure-only

Dependencies (see requirements.txt):
    boto3
    msal
    requests
"""

from __future__ import annotations

import argparse
import csv
import datetime
import os
import sys
from dataclasses import dataclass, field
from typing import Iterable


GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]

# Authentication method OData types that count as "not just a password."
# https://learn.microsoft.com/en-us/graph/api/resources/authenticationmethod
MFA_CAPABLE_METHOD_TYPES = {
    "#microsoft.graph.microsoftAuthenticatorAuthenticationMethod",
    "#microsoft.graph.phoneAuthenticationMethod",
    "#microsoft.graph.fido2AuthenticationMethod",
    "#microsoft.graph.softwareOathAuthenticationMethod",
    "#microsoft.graph.windowsHelloForBusinessAuthenticationMethod",
    "#microsoft.graph.temporaryAccessPassAuthenticationMethod",
    "#microsoft.graph.platformCredentialAuthenticationMethod",
    "#microsoft.graph.emailAuthenticationMethod",
}


@dataclass
class ComplianceRow:
    source: str  # "AWS" or "Azure"
    identity: str
    display_name: str
    mfa_enabled: bool
    mfa_methods: str
    account_created: str
    notes: str = ""


# ---------------------------------------------------------------------------
# AWS IAM
# ---------------------------------------------------------------------------
def get_aws_mfa_status(region: str | None = None) -> list[ComplianceRow]:
    """Enumerate IAM users and check whether each has an MFA device attached."""
    import boto3  # imported here so --azure-only doesn't require boto3 to be installed

    session = boto3.Session(region_name=region) if region else boto3.Session()
    iam = session.client("iam")

    rows: list[ComplianceRow] = []
    paginator = iam.get_paginator("list_users")

    for page in paginator.paginate():
        for user in page["Users"]:
            username = user["UserName"]
            created = user["CreateDate"].strftime("%Y-%m-%d")

            mfa_devices = iam.list_mfa_devices(UserName=username).get("MFADevices", [])
            mfa_enabled = len(mfa_devices) > 0
            methods = ", ".join(d["SerialNumber"] for d in mfa_devices) if mfa_devices else "none"

            rows.append(
                ComplianceRow(
                    source="AWS",
                    identity=username,
                    display_name=username,
                    mfa_enabled=mfa_enabled,
                    mfa_methods=methods,
                    account_created=created,
                    notes="" if mfa_enabled else "No MFA device attached",
                )
            )

    return rows


# ---------------------------------------------------------------------------
# Microsoft Entra ID (Graph API)
# ---------------------------------------------------------------------------
def _get_graph_token(tenant_id: str, client_id: str, client_secret: str) -> str:
    import msal

    app = msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
    )

    result = app.acquire_token_for_client(scopes=GRAPH_SCOPE)
    if "access_token" not in result:
        error = result.get("error_description", result.get("error", "unknown error"))
        raise RuntimeError(f"Failed to acquire Graph token: {error}")

    return result["access_token"]


def _graph_get_paged(url: str, headers: dict, params: dict | None = None) -> Iterable[dict]:
    import requests

    while url:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        yield from data.get("value", [])
        url = data.get("@odata.nextLink")
        params = None  # nextLink already carries the query string


def get_azure_mfa_status(tenant_id: str, client_id: str, client_secret: str) -> list[ComplianceRow]:
    """Enumerate Entra ID users and check registered authentication methods for each."""
    import requests

    token = _get_graph_token(tenant_id, client_id, client_secret)
    headers = {"Authorization": f"Bearer {token}"}

    rows: list[ComplianceRow] = []

    users = _graph_get_paged(
        f"{GRAPH_BASE_URL}/users",
        headers,
        params={"$select": "id,displayName,userPrincipalName,createdDateTime,accountEnabled"},
    )

    for user in users:
        user_id = user["id"]
        upn = user.get("userPrincipalName", user_id)
        display_name = user.get("displayName", upn)
        created = (user.get("createdDateTime") or "")[:10]

        try:
            resp = requests.get(
                f"{GRAPH_BASE_URL}/users/{user_id}/authentication/methods",
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            methods_data = resp.json().get("value", [])
        except requests.HTTPError as exc:
            rows.append(
                ComplianceRow(
                    source="Azure",
                    identity=upn,
                    display_name=display_name,
                    mfa_enabled=False,
                    mfa_methods="unknown",
                    account_created=created,
                    notes=f"Could not read auth methods: {exc}",
                )
            )
            continue

        mfa_methods = [
            m.get("@odata.type", "unknown")
            for m in methods_data
            if m.get("@odata.type") in MFA_CAPABLE_METHOD_TYPES
        ]
        mfa_enabled = len(mfa_methods) > 0

        rows.append(
            ComplianceRow(
                source="Azure",
                identity=upn,
                display_name=display_name,
                mfa_enabled=mfa_enabled,
                mfa_methods=", ".join(m.split(".")[-1].replace("AuthenticationMethod", "") for m in mfa_methods)
                if mfa_methods
                else "none",
                account_created=created,
                notes="" if mfa_enabled else "No MFA-capable method registered",
            )
        )

    return rows


# ---------------------------------------------------------------------------
# Report output
# ---------------------------------------------------------------------------
def write_csv_report(rows: list[ComplianceRow], output_path: str) -> None:
    fieldnames = [
        "source",
        "identity",
        "display_name",
        "mfa_enabled",
        "mfa_methods",
        "account_created",
        "notes",
    ]

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "source": row.source,
                    "identity": row.identity,
                    "display_name": row.display_name,
                    "mfa_enabled": row.mfa_enabled,
                    "mfa_methods": row.mfa_methods,
                    "account_created": row.account_created,
                    "notes": row.notes,
                }
            )


def print_summary(rows: list[ComplianceRow]) -> None:
    if not rows:
        print("No identities found.")
        return

    for source in sorted({r.source for r in rows}):
        source_rows = [r for r in rows if r.source == source]
        non_compliant = [r for r in source_rows if not r.mfa_enabled]
        print(
            f"{source}: {len(source_rows)} identities, "
            f"{len(non_compliant)} without MFA "
            f"({len(source_rows) - len(non_compliant)} compliant)"
        )
        for r in non_compliant:
            print(f"    - {r.identity} ({r.notes})")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cross-cloud MFA compliance auditor.")
    parser.add_argument("--aws", action="store_true", help="Include AWS IAM users in the report.")
    parser.add_argument("--azure", action="store_true", help="Include Entra ID users in the report.")
    parser.add_argument(
        "--aws-only",
        action="store_true",
        help="Shortcut for --aws with Azure excluded, regardless of other flags.",
    )
    parser.add_argument(
        "--azure-only",
        action="store_true",
        help="Shortcut for --azure with AWS excluded, regardless of other flags.",
    )
    parser.add_argument(
        "--output",
        default=f"mfa_compliance_{datetime.date.today().isoformat()}.csv",
        help="Path to write the CSV report to (default: mfa_compliance_<today>.csv).",
    )
    parser.add_argument(
        "--aws-region",
        default=os.environ.get("AWS_REGION"),
        help="AWS region override (defaults to AWS_REGION env var / boto3's normal resolution).",
    )

    args = parser.parse_args(argv)

    if args.aws_only:
        args.aws, args.azure = True, False
    elif args.azure_only:
        args.aws, args.azure = False, True
    elif not args.aws and not args.azure:
        # Default to both if the user didn't specify anything.
        args.aws, args.azure = True, True

    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    all_rows: list[ComplianceRow] = []

    if args.aws:
        try:
            print("Auditing AWS IAM users...")
            all_rows.extend(get_aws_mfa_status(region=args.aws_region))
        except Exception as exc:  # noqa: BLE001 - report and continue to the other cloud
            print(f"AWS audit failed: {exc}", file=sys.stderr)

    if args.azure:
        tenant_id = os.environ.get("AZURE_TENANT_ID")
        client_id = os.environ.get("AZURE_CLIENT_ID")
        client_secret = os.environ.get("AZURE_CLIENT_SECRET")

        if not all([tenant_id, client_id, client_secret]):
            print(
                "AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET must all be set "
                "to audit Entra ID. Skipping Azure.",
                file=sys.stderr,
            )
        else:
            try:
                print("Auditing Entra ID users...")
                all_rows.extend(get_azure_mfa_status(tenant_id, client_id, client_secret))
            except Exception as exc:  # noqa: BLE001 - report and continue
                print(f"Azure audit failed: {exc}", file=sys.stderr)

    if not all_rows:
        print("No results collected from either cloud. Nothing written.", file=sys.stderr)
        return 1

    write_csv_report(all_rows, args.output)
    print(f"\nReport written to {args.output}\n")
    print_summary(all_rows)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
