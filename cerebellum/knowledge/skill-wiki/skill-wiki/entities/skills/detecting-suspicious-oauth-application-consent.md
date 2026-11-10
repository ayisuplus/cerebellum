---
title: detecting-suspicious-oauth-application-consent
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-azure-activity-logs-for-threats, detecting-aws-cloudtrail-anomalies, detecting-aws-iam-privilege-escalation, detecting-azure-lateral-movement, detecting-email-account-compromise, detecting-entra-offensive-tools-in-graph-logs, detecting-kerberoasting-attacks, detecting-misconfigured-azure-storage, detecting-mobile-malware-behavior, detecting-privilege-escalation-in-kubernetes-pods, detecting-service-account-abuse]
confidence: low
---

Detect risky OAuth application consent grants in Azure AD / Microsoft Entra ID using Microsoft Graph API, audit logs, and permission analysis to identify illicit consent grant attacks.

## Metadata

- **ID:** `detecting-suspicious-oauth-application-consent`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-suspicious-oauth-application-consent/SKILL.md`
- **Score:** 27.0
- **Edges:** 11

## Related Skills

- [[detecting-aws-cloudtrail-anomalies]] *(similar)* — Detect unusual API call patterns in AWS CloudTrail logs using boto3, statistical baselining, and behavioral analysis to identify credential compromise, privilege escalation, and unauthorized resource access.
- [[detecting-aws-iam-privilege-escalation]] *(similar)* — Detect AWS IAM privilege escalation paths using boto3 and Cloudsplaining policy analysis to identify overly permissive policies, dangerous permission combinations, and least-privilege violations
- [[detecting-kerberoasting-attacks]] *(similar)* — Detect Kerberoasting attacks by monitoring for anomalous Kerberos TGS requests targeting service accounts with SPNs for offline password cracking.
- [[detecting-mobile-malware-behavior]] *(similar)* — Detects and analyzes malicious behavior in mobile applications through behavioral analysis, permission abuse detection, network traffic monitoring, and dynamic instrumentation. Use when analyzing suspicious mobile applications for data exfiltration, command-and-control communication, credential stea
- [[detecting-privilege-escalation-in-kubernetes-pods]] *(similar)* — Detect and prevent privilege escalation in Kubernetes pods by monitoring security contexts, capabilities, and syscall patterns with Falco and OPA policies.
- [[detecting-azure-lateral-movement]] *(complement)* — Detect lateral movement in Azure AD/Entra ID environments using Microsoft Graph API audit logs, Azure Sentinel KQL hunting queries, and sign-in anomaly correlation to identify privilege escalation, token theft, and cross-tenant pivoting.
- [[detecting-email-account-compromise]] *(complement)* — Detect compromised O365 and Google Workspace email accounts by analyzing inbox rule creation, suspicious sign-in locations, mail forwarding rules, and unusual API access patterns via Microsoft Graph and audit logs.
- [[analyzing-azure-activity-logs-for-threats]] *(similar)* — Queries Azure Monitor activity logs and sign-in logs via azure-monitor-query to detect suspicious administrative operations, impossible travel, privilege escalation, and resource modifications. Builds KQL queries for threat hunting in Azure environments. Use when investigating suspicious Azure tenan
- [[detecting-entra-offensive-tools-in-graph-logs]] *(similar)* — Hunt AADGraphActivityLogs and MicrosoftGraphActivityLogs in Microsoft Sentinel/Log Analytics for fingerprints of offensive Entra ID tools such as ROADtools, AADInternals, and AzureHound.
- [[detecting-misconfigured-azure-storage]] *(similar)* — Detecting misconfigured Azure Storage accounts including publicly accessible blob containers, missing encryption settings, overly permissive SAS tokens, disabled logging, and network access violations using Azure CLI, PowerShell, and Microsoft Defender for Storage.

- [[detecting-service-account-abuse]] *(similar)* — Detect abuse of service accounts through anomalous interactive logons, privilege escalation, lateral movement, and unauthorized access patterns.

## See Also

- [[abusing-dpapi-for-credential-access]] — Anthropic-Cybersecurity-Skills
- [[abusing-shadow-credentials-for-privesc]] — Anthropic-Cybersecurity-Skills
- [[achieving-cmmc-level-2-compliance]] — Anthropic-Cybersecurity-Skills
- [[acquiring-disk-image-with-dd-and-dcfldd]] — Anthropic-Cybersecurity-Skills
- [[analyzing-active-directory-acl-abuse]] — Anthropic-Cybersecurity-Skills
- [[analyzing-android-malware-with-apktool]] — Anthropic-Cybersecurity-Skills
- [[analyzing-api-gateway-access-logs]] — Anthropic-Cybersecurity-Skills
- [[analyzing-apt-group-with-mitre-navigator]] — Anthropic-Cybersecurity-Skills
- [[analyzing-bootkit-and-rootkit-samples]] — Anthropic-Cybersecurity-Skills
- [[analyzing-campaign-attribution-evidence]] — Anthropic-Cybersecurity-Skills
