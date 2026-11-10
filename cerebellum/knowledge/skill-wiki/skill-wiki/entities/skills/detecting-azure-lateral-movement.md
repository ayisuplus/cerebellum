---
title: detecting-azure-lateral-movement
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-azure-activity-logs-for-threats, auditing-azure-active-directory-configuration, deploying-active-directory-honeytokens, detecting-azure-service-principal-abuse, detecting-email-account-compromise, detecting-entra-offensive-tools-in-graph-logs, detecting-lateral-movement-with-zeek, detecting-misconfigured-azure-storage, detecting-pass-the-hash-attacks, detecting-service-account-abuse, detecting-suspicious-oauth-application-consent, extracting-windows-event-logs-artifacts, hunting-for-ntlm-relay-attacks, implementing-siem-correlation-rules-for-apt]
confidence: low
---

Detect lateral movement in Azure AD/Entra ID environments using Microsoft Graph API audit logs, Azure Sentinel KQL hunting queries, and sign-in anomaly correlation to identify privilege escalation, token theft, and cross-tenant pivoting.

## Metadata

- **ID:** `detecting-azure-lateral-movement`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-azure-lateral-movement/SKILL.md`
- **Score:** 21.0
- **Edges:** 14

## Related Skills

- [[detecting-azure-service-principal-abuse]] *(bridge)* — Detect and investigate Azure service principal abuse including privilege escalation, credential compromise, admin consent bypass, and unauthorized enumeration in Microsoft Entra ID environments.
- [[detecting-email-account-compromise]] *(complement)* — Detect compromised O365 and Google Workspace email accounts by analyzing inbox rule creation, suspicious sign-in locations, mail forwarding rules, and unusual API access patterns via Microsoft Graph and audit logs.
- [[detecting-entra-offensive-tools-in-graph-logs]] *(complement)* — Hunt AADGraphActivityLogs and MicrosoftGraphActivityLogs in Microsoft Sentinel/Log Analytics for fingerprints of offensive Entra ID tools such as ROADtools, AADInternals, and AzureHound.
- [[detecting-service-account-abuse]] *(complement)* — Detect abuse of service accounts through anomalous interactive logons, privilege escalation, lateral movement, and unauthorized access patterns.
- [[detecting-suspicious-oauth-application-consent]] *(complement)* — Detect risky OAuth application consent grants in Azure AD / Microsoft Entra ID using Microsoft Graph API, audit logs, and permission analysis to identify illicit consent grant attacks.
- [[detecting-lateral-movement-with-zeek]] *(similar)* — Detect lateral movement in network traffic using Zeek (formerly Bro) log analysis. Parses conn.log, smb_mapping.log, smb_files.log, dce_rpc.log, kerberos.log, and ntlm.log to identify SMB file transfers, NTLM account spray activity, remote service execution, and anomalous internal connections.

- [[auditing-azure-active-directory-configuration]] *(bridge)* — Auditing Microsoft Entra ID (Azure Active Directory) configuration to identify risky authentication policies, overly permissive role assignments, stale accounts, conditional access gaps, and guest user risks using AzureAD PowerShell, Microsoft Graph API, and ScoutSuite.

- [[analyzing-azure-activity-logs-for-threats]] *(complement)* — Queries Azure Monitor activity logs and sign-in logs via azure-monitor-query to detect suspicious administrative operations, impossible travel, privilege escalation, and resource modifications. Builds KQL queries for threat hunting in Azure environments. Use when investigating suspicious Azure tenan
- [[deploying-active-directory-honeytokens]] *(similar)* — Deploys deception-based honeytokens in Active Directory including fake privileged accounts with AdminCount=1, fake SPNs for Kerberoasting detection (honeyroasting), decoy GPOs with cpassword traps, and fake BloodHound paths. Monitors Windows Security Event IDs 4769, 4625, 4662, 5136 for honeytoken i
- [[detecting-misconfigured-azure-storage]] *(similar)* — Detecting misconfigured Azure Storage accounts including publicly accessible blob containers, missing encryption settings, overly permissive SAS tokens, disabled logging, and network access violations using Azure CLI, PowerShell, and Microsoft Defender for Storage.

- [[detecting-pass-the-hash-attacks]] *(similar)* — Detect Pass-the-Hash attacks by analyzing NTLM authentication patterns, identifying Type 3 logons with NTLM where Kerberos is expected, and correlating with credential dumping.
- [[extracting-windows-event-logs-artifacts]] *(similar)* — Extract, parse, and analyze Windows Event Logs (EVTX) using Chainsaw, Hayabusa, and EvtxECmd to detect lateral movement, persistence, and privilege escalation.
- [[hunting-for-ntlm-relay-attacks]] *(similar)* — Detect NTLM relay attacks by analyzing Windows Event 4624 logon type 3 with NTLMSSP authentication, identifying IP-to-hostname mismatches, Responder traffic signatures, SMB signing status, and suspicious authentication patterns across the domain.
- [[implementing-siem-correlation-rules-for-apt]] *(similar)* — Write multi-event correlation rules that detect APT lateral movement by chaining Windows authentication events, process execution telemetry, and network connection logs across hosts. Uses Splunk SPL and Sigma rule format to correlate Event IDs 4624, 4648, 4688, and Sysmon Events 1/3 within sliding t

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
