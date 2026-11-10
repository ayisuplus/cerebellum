---
title: hunting-for-suspicious-scheduled-tasks
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [detecting-dll-sideloading-attacks, detecting-suspicious-powershell-execution, detecting-t1548-abuse-elevation-control-mechanism, hunting-for-data-exfiltration-indicators, hunting-for-dcom-lateral-movement, hunting-for-dcsync-attacks, hunting-for-dns-based-persistence, hunting-for-living-off-the-cloud-techniques, hunting-for-t1098-account-manipulation, hunting-saas-sso-token-abuse, performing-active-directory-compromise-investigation]
confidence: low
---

Hunt for adversary persistence and execution via Windows scheduled tasks by analyzing task creation events, suspicious task properties, and unusual execution patterns that indicate T1053.005 abuse.

## Metadata

- **ID:** `hunting-for-suspicious-scheduled-tasks`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/hunting-for-suspicious-scheduled-tasks/SKILL.md`
- **Score:** 39.0
- **Edges:** 11

## Related Skills

- [[hunting-for-data-exfiltration-indicators]] *(similar)* — Hunt for data exfiltration through network traffic analysis, detecting unusual data flows, DNS tunneling, cloud storage uploads, and encrypted channel abuse.
- [[hunting-for-living-off-the-cloud-techniques]] *(similar)* — Hunt for adversary abuse of legitimate cloud services for C2, data staging, and exfiltration including abuse of Azure, AWS, GCP services, and SaaS platforms.
- [[hunting-for-t1098-account-manipulation]] *(similar)* — Hunt for MITRE ATT&CK T1098 account manipulation including shadow admin creation, SID history injection, group membership changes, and credential modifications using Windows Security Event Logs.
- [[hunting-saas-sso-token-abuse]] *(similar)* — Detect SSO and OAuth token replay and SaaS lateral movement.
- [[performing-active-directory-compromise-investigation]] *(similar)* — Investigate Active Directory compromise by analyzing authentication logs, replication metadata, Group Policy changes, and Kerberos ticket anomalies to identify attacker persistence and lateral movement paths.
- [[detecting-dll-sideloading-attacks]] *(similar)* — Detect DLL side-loading attacks where adversaries place malicious DLLs alongside legitimate applications to hijack execution flow for defense evasion.
- [[detecting-suspicious-powershell-execution]] *(similar)* — Detect suspicious PowerShell execution patterns including encoded commands, download cradles, AMSI bypass attempts, and constrained language mode evasion.
- [[detecting-t1548-abuse-elevation-control-mechanism]] *(similar)* — Detect abuse of elevation control mechanisms including UAC bypass, sudo exploitation, and setuid/setgid manipulation by monitoring registry modifications, process elevation flags, and unusual parent-child process relationships.
- [[hunting-for-dcom-lateral-movement]] *(similar)* — Hunt for DCOM-based lateral movement by detecting abuse of MMC20.Application, ShellBrowserWindow, and ShellWindows COM objects through Sysmon Event ID 1 (process creation) and Event ID 3 (network connection) correlation, WMI event analysis, RPC endpoint mapper traffic on port 135, and DCOM-specific 
- [[hunting-for-dcsync-attacks]] *(similar)* — Detect DCSync attacks by analyzing Windows Event ID 4662 for unauthorized DS-Replication-Get-Changes requests from non-domain-controller accounts.
- [[hunting-for-dns-based-persistence]] *(similar)* — Hunt for DNS-based persistence mechanisms including DNS hijacking, dangling CNAME records, wildcard DNS abuse, and unauthorized zone modifications using passive DNS databases, SecurityTrails API, and DNS audit log analysis.

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
