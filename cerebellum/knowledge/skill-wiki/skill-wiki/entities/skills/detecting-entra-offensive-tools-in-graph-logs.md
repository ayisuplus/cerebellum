---
title: detecting-entra-offensive-tools-in-graph-logs
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-azure-activity-logs-for-threats, detecting-azure-lateral-movement, detecting-email-account-compromise, detecting-service-account-abuse, detecting-suspicious-oauth-application-consent, hunting-for-spearphishing-indicators]
confidence: low
---

Hunt AADGraphActivityLogs and MicrosoftGraphActivityLogs in Microsoft Sentinel/Log Analytics for fingerprints of offensive Entra ID tools such as ROADtools, AADInternals, and AzureHound.

## Metadata

- **ID:** `detecting-entra-offensive-tools-in-graph-logs`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-entra-offensive-tools-in-graph-logs/SKILL.md`
- **Score:** 39.0
- **Edges:** 6

## Related Skills

- [[analyzing-azure-activity-logs-for-threats]] *(similar)* — Queries Azure Monitor activity logs and sign-in logs via azure-monitor-query to detect suspicious administrative operations, impossible travel, privilege escalation, and resource modifications. Builds KQL queries for threat hunting in Azure environments. Use when investigating suspicious Azure tenan
- [[detecting-email-account-compromise]] *(similar)* — Detect compromised O365 and Google Workspace email accounts by analyzing inbox rule creation, suspicious sign-in locations, mail forwarding rules, and unusual API access patterns via Microsoft Graph and audit logs.
- [[detecting-service-account-abuse]] *(similar)* — Detect abuse of service accounts through anomalous interactive logons, privilege escalation, lateral movement, and unauthorized access patterns.
- [[detecting-suspicious-oauth-application-consent]] *(similar)* — Detect risky OAuth application consent grants in Azure AD / Microsoft Entra ID using Microsoft Graph API, audit logs, and permission analysis to identify illicit consent grant attacks.
- [[hunting-for-spearphishing-indicators]] *(similar)* — Hunt for spearphishing campaign indicators across email logs, endpoint telemetry, and network data to detect targeted email attacks.
- [[detecting-azure-lateral-movement]] *(complement)* — Detect lateral movement in Azure AD/Entra ID environments using Microsoft Graph API audit logs, Azure Sentinel KQL hunting queries, and sign-in anomaly correlation to identify privilege escalation, token theft, and cross-tenant pivoting.

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
