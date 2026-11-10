---
title: auditing-azure-active-directory-configuration
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [auditing-entra-id-with-aadinternals, auditing-gcp-iam-permissions, auditing-terraform-infrastructure-for-security, detecting-azure-lateral-movement, implementing-azure-ad-privileged-identity-management, implementing-device-posture-assessment-in-zero-trust, performing-aws-account-enumeration-with-scout-suite, performing-oauth-scope-minimization-review, performing-service-account-audit]
confidence: medium
---

Auditing Microsoft Entra ID (Azure Active Directory) configuration to identify risky authentication policies, overly permissive role assignments, stale accounts, conditional access gaps, and guest user risks using AzureAD PowerShell, Microsoft Graph API, and ScoutSuite.

## Metadata

- **ID:** `auditing-azure-active-directory-configuration`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/auditing-azure-active-directory-configuration/SKILL.md`
- **Score:** 45.0
- **Edges:** 9

## Related Skills

- [[auditing-entra-id-with-aadinternals]] *(bridge)* — Run Microsoft Entra ID tenant reconnaissance, token acquisition and manipulation, and federation backdoor testing with the AADInternals PowerShell toolkit to validate identity-attack resilience.
- [[detecting-azure-lateral-movement]] *(bridge)* — Detect lateral movement in Azure AD/Entra ID environments using Microsoft Graph API audit logs, Azure Sentinel KQL hunting queries, and sign-in anomaly correlation to identify privilege escalation, token theft, and cross-tenant pivoting.
- [[auditing-gcp-iam-permissions]] *(similar)* — Auditing Google Cloud Platform IAM permissions to identify overly permissive bindings, primitive role usage, service account key proliferation, and cross-project access risks using gcloud CLI, Policy Analyzer, and IAM Recommender.

- [[auditing-terraform-infrastructure-for-security]] *(similar)* — Auditing Terraform infrastructure-as-code for security misconfigurations using Checkov, tfsec, Terrascan, and OPA/Rego policies to detect overly permissive IAM policies, public resource exposure, missing encryption, and insecure defaults before cloud deployment.

- [[implementing-azure-ad-privileged-identity-management]] *(similar)* — Configure Microsoft Entra Privileged Identity Management to enforce just-in-time role activation, approval workflows, and access reviews for Azure AD privileged roles.
- [[performing-aws-account-enumeration-with-scout-suite]] *(similar)* — Perform comprehensive security posture assessment of AWS accounts using ScoutSuite to enumerate resources, identify misconfigurations, and generate actionable security reports.
- [[performing-service-account-audit]] *(similar)* — Audit service accounts across enterprise infrastructure to identify orphaned, over-privileged, and non-compliant accounts. This skill covers discovery of service accounts in Active Directory, cloud pl
- [[implementing-device-posture-assessment-in-zero-trust]] *(similar)* — Implementing device posture assessment as a zero trust access control by integrating endpoint health signals from CrowdStrike ZTA, Microsoft Intune, and Jamf into conditional access policies that enforce compliance before granting resource access.

- [[performing-oauth-scope-minimization-review]] *(similar)* — Performs OAuth 2.0 scope minimization review to identify over-permissioned third-party application integrations, excessive API scopes, unused token grants, and risky OAuth consent patterns across identity providers and SaaS platforms. Activates for requests involving OAuth scope audit, API permissio

## See Also

- [[abusing-dpapi-for-credential-access]] — Anthropic-Cybersecurity-Skills
- [[abusing-shadow-credentials-for-privesc]] — Anthropic-Cybersecurity-Skills
- [[achieving-cmmc-level-2-compliance]] — Anthropic-Cybersecurity-Skills
- [[acquiring-disk-image-with-dd-and-dcfldd]] — Anthropic-Cybersecurity-Skills
- [[analyzing-active-directory-acl-abuse]] — Anthropic-Cybersecurity-Skills
- [[analyzing-android-malware-with-apktool]] — Anthropic-Cybersecurity-Skills
- [[analyzing-api-gateway-access-logs]] — Anthropic-Cybersecurity-Skills
- [[analyzing-apt-group-with-mitre-navigator]] — Anthropic-Cybersecurity-Skills
- [[analyzing-azure-activity-logs-for-threats]] — Anthropic-Cybersecurity-Skills
- [[analyzing-bootkit-and-rootkit-samples]] — Anthropic-Cybersecurity-Skills
