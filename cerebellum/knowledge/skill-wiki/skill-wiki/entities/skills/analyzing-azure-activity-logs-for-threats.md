---
title: analyzing-azure-activity-logs-for-threats
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-kubernetes-audit-logs, detecting-azure-lateral-movement, detecting-email-account-compromise, detecting-entra-offensive-tools-in-graph-logs, detecting-service-account-abuse, detecting-suspicious-oauth-application-consent, implementing-cloud-trail-log-analysis, performing-threat-hunting-with-elastic-siem, performing-user-behavior-analytics]
confidence: low
---

Queries Azure Monitor activity logs and sign-in logs via azure-monitor-query to detect suspicious administrative operations, impossible travel, privilege escalation, and resource modifications. Builds KQL queries for threat hunting in Azure environments. Use when investigating suspicious Azure tenan

## Metadata

- **ID:** `analyzing-azure-activity-logs-for-threats`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/analyzing-azure-activity-logs-for-threats/SKILL.md`
- **Score:** 33.0
- **Edges:** 9

## Related Skills

- [[detecting-azure-lateral-movement]] *(complement)* — Detect lateral movement in Azure AD/Entra ID environments using Microsoft Graph API audit logs, Azure Sentinel KQL hunting queries, and sign-in anomaly correlation to identify privilege escalation, token theft, and cross-tenant pivoting.
- [[analyzing-kubernetes-audit-logs]] *(similar)* — Parses Kubernetes API server audit logs (JSON lines) to detect exec-into-pod, secret access, RBAC modifications, privileged pod creation, and anonymous API access. Builds threat detection rules from audit event patterns. Use when investigating Kubernetes cluster compromise or building k8s-specific S
- [[detecting-email-account-compromise]] *(similar)* — Detect compromised O365 and Google Workspace email accounts by analyzing inbox rule creation, suspicious sign-in locations, mail forwarding rules, and unusual API access patterns via Microsoft Graph and audit logs.
- [[detecting-service-account-abuse]] *(similar)* — Detect abuse of service accounts through anomalous interactive logons, privilege escalation, lateral movement, and unauthorized access patterns.
- [[detecting-suspicious-oauth-application-consent]] *(similar)* — Detect risky OAuth application consent grants in Azure AD / Microsoft Entra ID using Microsoft Graph API, audit logs, and permission analysis to identify illicit consent grant attacks.
- [[detecting-entra-offensive-tools-in-graph-logs]] *(similar)* — Hunt AADGraphActivityLogs and MicrosoftGraphActivityLogs in Microsoft Sentinel/Log Analytics for fingerprints of offensive Entra ID tools such as ROADtools, AADInternals, and AzureHound.
- [[implementing-cloud-trail-log-analysis]] *(similar)* — Implementing AWS CloudTrail log analysis for security monitoring, threat detection, and forensic investigation using Athena, CloudWatch Logs Insights, and SIEM integration to identify unauthorized access, privilege escalation, and suspicious API activity.

- [[performing-threat-hunting-with-elastic-siem]] *(similar)* — Performs proactive threat hunting in Elastic Security SIEM using KQL/EQL queries, detection rules, and Timeline investigation to identify threats that evade automated detection. Use when SOC teams need to hunt for specific ATT&CK techniques, investigate anomalous behaviors, or validate detection cov
- [[performing-user-behavior-analytics]] *(similar)* — Performs User and Entity Behavior Analytics (UEBA) to detect anomalous user activities including impossible travel, unusual access patterns, privilege abuse, and insider threats using SIEM-based behavioral baselines and statistical analysis. Use when SOC teams need to identify compromised accounts o

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
