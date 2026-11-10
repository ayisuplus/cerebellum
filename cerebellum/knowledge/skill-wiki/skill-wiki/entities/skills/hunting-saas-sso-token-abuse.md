---
title: hunting-saas-sso-token-abuse
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [attacking-oauth-with-device-code-phishing, detecting-azure-service-principal-abuse, detecting-insider-threat-with-ueba, detecting-oauth-token-theft, detecting-privilege-escalation-attempts, exploiting-oauth-misconfiguration, hunting-for-data-exfiltration-indicators, hunting-for-dcom-lateral-movement, hunting-for-dcsync-attacks, hunting-for-dns-based-persistence, hunting-for-living-off-the-cloud-techniques, hunting-for-suspicious-scheduled-tasks, hunting-for-t1098-account-manipulation]
confidence: low
---

Detect SSO and OAuth token replay and SaaS lateral movement.

## Metadata

- **ID:** `hunting-saas-sso-token-abuse`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/hunting-saas-sso-token-abuse/SKILL.md`
- **Score:** 37.0
- **Edges:** 13

## Related Skills

- [[attacking-oauth-with-device-code-phishing]] *(similar)* — Run OAuth 2.0 device-code and illicit-consent phishing against Microsoft Entra ID to steal access and refresh tokens, bypass MFA, and pivot across Microsoft 365 services.
- [[detecting-privilege-escalation-attempts]] *(similar)* — Detect privilege escalation attempts including token manipulation, UAC bypass, unquoted service paths, kernel exploits, and sudo/doas abuse across Windows and Linux.
- [[exploiting-oauth-misconfiguration]] *(similar)* — Identifying and exploiting OAuth 2.0 and OpenID Connect misconfigurations including redirect URI manipulation, token leakage, and authorization code theft during security assessments.
- [[hunting-for-dcsync-attacks]] *(similar)* — Detect DCSync attacks by analyzing Windows Event ID 4662 for unauthorized DS-Replication-Get-Changes requests from non-domain-controller accounts.
- [[hunting-for-dns-based-persistence]] *(similar)* — Hunt for DNS-based persistence mechanisms including DNS hijacking, dangling CNAME records, wildcard DNS abuse, and unauthorized zone modifications using passive DNS databases, SecurityTrails API, and DNS audit log analysis.
- [[detecting-azure-service-principal-abuse]] *(similar)* — Detect and investigate Azure service principal abuse including privilege escalation, credential compromise, admin consent bypass, and unauthorized enumeration in Microsoft Entra ID environments.
- [[detecting-insider-threat-with-ueba]] *(similar)* — Implement User and Entity Behavior Analytics using Elasticsearch/OpenSearch to build behavioral baselines, calculate anomaly scores, perform peer group analysis, and detect insider threat indicators such as data exfiltration, privilege abuse, and unauthorized access patterns.
- [[detecting-oauth-token-theft]] *(similar)* — Detects and responds to OAuth token theft and replay attacks in cloud environments, focusing on Microsoft Entra ID (Azure AD) token protection, conditional access policies, and sign-in anomaly detection. Covers access token theft, refresh token replay, Primary Refresh Token (PRT) abuse, and pass-the
- [[hunting-for-data-exfiltration-indicators]] *(similar)* — Hunt for data exfiltration through network traffic analysis, detecting unusual data flows, DNS tunneling, cloud storage uploads, and encrypted channel abuse.
- [[hunting-for-dcom-lateral-movement]] *(similar)* — Hunt for DCOM-based lateral movement by detecting abuse of MMC20.Application, ShellBrowserWindow, and ShellWindows COM objects through Sysmon Event ID 1 (process creation) and Event ID 3 (network connection) correlation, WMI event analysis, RPC endpoint mapper traffic on port 135, and DCOM-specific 
- [[hunting-for-living-off-the-cloud-techniques]] *(similar)* — Hunt for adversary abuse of legitimate cloud services for C2, data staging, and exfiltration including abuse of Azure, AWS, GCP services, and SaaS platforms.
- [[hunting-for-suspicious-scheduled-tasks]] *(similar)* — Hunt for adversary persistence and execution via Windows scheduled tasks by analyzing task creation events, suspicious task properties, and unusual execution patterns that indicate T1053.005 abuse.
- [[hunting-for-t1098-account-manipulation]] *(similar)* — Hunt for MITRE ATT&CK T1098 account manipulation including shadow admin creation, SID history injection, group membership changes, and credential modifications using Windows Security Event Logs.

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
