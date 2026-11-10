---
title: hunting-for-dcsync-attacks
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-active-directory-acl-abuse, conducting-domain-persistence-with-dcsync, detecting-suspicious-powershell-execution, hunting-for-data-exfiltration-indicators, hunting-for-dcom-lateral-movement, hunting-for-dns-based-persistence, hunting-for-suspicious-scheduled-tasks, hunting-for-t1098-account-manipulation, hunting-saas-sso-token-abuse, investigating-ransomware-attack-artifacts, performing-active-directory-compromise-investigation]
confidence: low
---

Detect DCSync attacks by analyzing Windows Event ID 4662 for unauthorized DS-Replication-Get-Changes requests from non-domain-controller accounts.

## Metadata

- **ID:** `hunting-for-dcsync-attacks`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/hunting-for-dcsync-attacks/SKILL.md`
- **Score:** 33.0
- **Edges:** 11

## Related Skills

- [[analyzing-active-directory-acl-abuse]] *(similar)* — Detect dangerous ACL misconfigurations in Active Directory using ldap3 to identify GenericAll, WriteDACL, and WriteOwner abuse paths
- [[hunting-for-dns-based-persistence]] *(similar)* — Hunt for DNS-based persistence mechanisms including DNS hijacking, dangling CNAME records, wildcard DNS abuse, and unauthorized zone modifications using passive DNS databases, SecurityTrails API, and DNS audit log analysis.
- [[hunting-for-suspicious-scheduled-tasks]] *(similar)* — Hunt for adversary persistence and execution via Windows scheduled tasks by analyzing task creation events, suspicious task properties, and unusual execution patterns that indicate T1053.005 abuse.
- [[hunting-for-t1098-account-manipulation]] *(similar)* — Hunt for MITRE ATT&CK T1098 account manipulation including shadow admin creation, SID history injection, group membership changes, and credential modifications using Windows Security Event Logs.
- [[performing-active-directory-compromise-investigation]] *(similar)* — Investigate Active Directory compromise by analyzing authentication logs, replication metadata, Group Policy changes, and Kerberos ticket anomalies to identify attacker persistence and lateral movement paths.
- [[conducting-domain-persistence-with-dcsync]] *(similar)* — Perform DCSync attacks to replicate Active Directory credentials and establish domain persistence by extracting KRBTGT, Domain Admin, and service account hashes for Golden Ticket creation.
- [[detecting-suspicious-powershell-execution]] *(similar)* — Detect suspicious PowerShell execution patterns including encoded commands, download cradles, AMSI bypass attempts, and constrained language mode evasion.
- [[hunting-for-data-exfiltration-indicators]] *(similar)* — Hunt for data exfiltration through network traffic analysis, detecting unusual data flows, DNS tunneling, cloud storage uploads, and encrypted channel abuse.
- [[hunting-for-dcom-lateral-movement]] *(similar)* — Hunt for DCOM-based lateral movement by detecting abuse of MMC20.Application, ShellBrowserWindow, and ShellWindows COM objects through Sysmon Event ID 1 (process creation) and Event ID 3 (network connection) correlation, WMI event analysis, RPC endpoint mapper traffic on port 135, and DCOM-specific 
- [[hunting-saas-sso-token-abuse]] *(similar)* — Detect SSO and OAuth token replay and SaaS lateral movement.
- [[investigating-ransomware-attack-artifacts]] *(similar)* — Identify, collect, and analyze ransomware attack artifacts to determine the variant, initial access vector, encryption scope, and recovery options.

## See Also

- [[abusing-dpapi-for-credential-access]] — Anthropic-Cybersecurity-Skills
- [[abusing-shadow-credentials-for-privesc]] — Anthropic-Cybersecurity-Skills
- [[achieving-cmmc-level-2-compliance]] — Anthropic-Cybersecurity-Skills
- [[acquiring-disk-image-with-dd-and-dcfldd]] — Anthropic-Cybersecurity-Skills
- [[analyzing-android-malware-with-apktool]] — Anthropic-Cybersecurity-Skills
- [[analyzing-api-gateway-access-logs]] — Anthropic-Cybersecurity-Skills
- [[analyzing-apt-group-with-mitre-navigator]] — Anthropic-Cybersecurity-Skills
- [[analyzing-azure-activity-logs-for-threats]] — Anthropic-Cybersecurity-Skills
- [[analyzing-bootkit-and-rootkit-samples]] — Anthropic-Cybersecurity-Skills
- [[analyzing-campaign-attribution-evidence]] — Anthropic-Cybersecurity-Skills
