---
title: hunting-for-t1098-account-manipulation
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-active-directory-acl-abuse, detecting-azure-service-principal-abuse, detecting-t1548-abuse-elevation-control-mechanism, hunting-for-dcom-lateral-movement, hunting-for-dcsync-attacks, hunting-for-suspicious-scheduled-tasks, hunting-saas-sso-token-abuse, performing-active-directory-compromise-investigation, performing-active-directory-forest-trust-attack]
confidence: low
---

Hunt for MITRE ATT&CK T1098 account manipulation including shadow admin creation, SID history injection, group membership changes, and credential modifications using Windows Security Event Logs.

## Metadata

- **ID:** `hunting-for-t1098-account-manipulation`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/hunting-for-t1098-account-manipulation/SKILL.md`
- **Score:** 21.0
- **Edges:** 9

## Related Skills

- [[analyzing-active-directory-acl-abuse]] *(similar)* — Detect dangerous ACL misconfigurations in Active Directory using ldap3 to identify GenericAll, WriteDACL, and WriteOwner abuse paths
- [[detecting-azure-service-principal-abuse]] *(similar)* — Detect and investigate Azure service principal abuse including privilege escalation, credential compromise, admin consent bypass, and unauthorized enumeration in Microsoft Entra ID environments.
- [[hunting-saas-sso-token-abuse]] *(similar)* — Detect SSO and OAuth token replay and SaaS lateral movement.
- [[performing-active-directory-compromise-investigation]] *(similar)* — Investigate Active Directory compromise by analyzing authentication logs, replication metadata, Group Policy changes, and Kerberos ticket anomalies to identify attacker persistence and lateral movement paths.
- [[performing-active-directory-forest-trust-attack]] *(similar)* — Enumerate and audit Active Directory forest trust relationships using impacket for SID filtering analysis, trust key extraction, cross-forest SID history abuse detection, and inter-realm Kerberos ticket assessment.
- [[detecting-t1548-abuse-elevation-control-mechanism]] *(similar)* — Detect abuse of elevation control mechanisms including UAC bypass, sudo exploitation, and setuid/setgid manipulation by monitoring registry modifications, process elevation flags, and unusual parent-child process relationships.
- [[hunting-for-dcom-lateral-movement]] *(similar)* — Hunt for DCOM-based lateral movement by detecting abuse of MMC20.Application, ShellBrowserWindow, and ShellWindows COM objects through Sysmon Event ID 1 (process creation) and Event ID 3 (network connection) correlation, WMI event analysis, RPC endpoint mapper traffic on port 135, and DCOM-specific 
- [[hunting-for-dcsync-attacks]] *(similar)* — Detect DCSync attacks by analyzing Windows Event ID 4662 for unauthorized DS-Replication-Get-Changes requests from non-domain-controller accounts.
- [[hunting-for-suspicious-scheduled-tasks]] *(similar)* — Hunt for adversary persistence and execution via Windows scheduled tasks by analyzing task creation events, suspicious task properties, and unusual execution patterns that indicate T1053.005 abuse.

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
