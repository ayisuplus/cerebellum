---
title: detecting-pass-the-hash-attacks
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [deploying-active-directory-honeytokens, detecting-anomalous-authentication-patterns, detecting-azure-lateral-movement, detecting-credential-dumping-techniques, detecting-golden-ticket-forgery, detecting-kerberoasting-attacks, detecting-lateral-movement-with-zeek, detecting-living-off-the-land-attacks, detecting-mimikatz-execution-patterns, detecting-rdp-brute-force-attacks, detecting-service-account-abuse, hunting-credential-stuffing-attacks, hunting-for-ntlm-relay-attacks, implementing-siem-correlation-rules-for-apt]
confidence: low
---

Detect Pass-the-Hash attacks by analyzing NTLM authentication patterns, identifying Type 3 logons with NTLM where Kerberos is expected, and correlating with credential dumping.

## Metadata

- **ID:** `detecting-pass-the-hash-attacks`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-pass-the-hash-attacks/SKILL.md`
- **Score:** 33.0
- **Edges:** 14

## Related Skills

- [[detecting-rdp-brute-force-attacks]] *(complement)* — Detect RDP brute force attacks by analyzing Windows Security Event Logs for failed authentication patterns (Event ID 4625), successful logons after failures (Event ID 4624), NLA failures, and source IP frequency analysis.
- [[hunting-for-ntlm-relay-attacks]] *(complement)* — Detect NTLM relay attacks by analyzing Windows Event 4624 logon type 3 with NTLMSSP authentication, identifying IP-to-hostname mismatches, Responder traffic signatures, SMB signing status, and suspicious authentication patterns across the domain.
- [[detecting-anomalous-authentication-patterns]] *(similar)* — Detects anomalous authentication patterns using UEBA analytics, statistical baselines, and machine learning models to identify impossible travel, credential stuffing, brute force, password spraying, and compromised account behaviors across authentication logs. Activates for requests involving authen
- [[detecting-azure-lateral-movement]] *(similar)* — Detect lateral movement in Azure AD/Entra ID environments using Microsoft Graph API audit logs, Azure Sentinel KQL hunting queries, and sign-in anomaly correlation to identify privilege escalation, token theft, and cross-tenant pivoting.
- [[detecting-service-account-abuse]] *(similar)* — Detect abuse of service accounts through anomalous interactive logons, privilege escalation, lateral movement, and unauthorized access patterns.
- [[detecting-credential-dumping-techniques]] *(complement)* — Detect LSASS credential dumping, SAM database extraction, and NTDS.dit theft using Sysmon Event ID 10, Windows Security logs, and SIEM correlation rules
- [[detecting-kerberoasting-attacks]] *(complement)* — Detect Kerberoasting attacks by monitoring for anomalous Kerberos TGS requests targeting service accounts with SPNs for offline password cracking.
- [[detecting-mimikatz-execution-patterns]] *(complement)* — Detect Mimikatz execution through command-line patterns, LSASS access signatures, binary indicators, and in-memory detection of known modules.
- [[deploying-active-directory-honeytokens]] *(similar)* — Deploys deception-based honeytokens in Active Directory including fake privileged accounts with AdminCount=1, fake SPNs for Kerberoasting detection (honeyroasting), decoy GPOs with cpassword traps, and fake BloodHound paths. Monitors Windows Security Event IDs 4769, 4625, 4662, 5136 for honeytoken i
- [[detecting-golden-ticket-forgery]] *(similar)* — Detect Kerberos Golden Ticket forgery by analyzing Windows Event ID 4769 for RC4 encryption downgrades (0x17), abnormal ticket lifetimes, and krbtgt account anomalies in Splunk and Elastic SIEM
- [[detecting-lateral-movement-with-zeek]] *(similar)* — Detect lateral movement in network traffic using Zeek (formerly Bro) log analysis. Parses conn.log, smb_mapping.log, smb_files.log, dce_rpc.log, kerberos.log, and ntlm.log to identify SMB file transfers, NTLM account spray activity, remote service execution, and anomalous internal connections.

- [[detecting-living-off-the-land-attacks]] *(similar)* — Detect abuse of legitimate Windows binaries (LOLBins) used for living off the land attacks. Monitors process creation, command-line arguments, and parent-child relationships to identify suspicious LOLBin execution patterns.

- [[hunting-credential-stuffing-attacks]] *(similar)* — Detects credential stuffing attacks by analyzing authentication logs for login velocity anomalies, ASN diversity, password spray patterns, and geographic distribution of failed logins. Uses statistical analysis on Splunk or raw log data. Use when investigating account takeover campaigns or building 
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
- [[analyzing-azure-activity-logs-for-threats]] — Anthropic-Cybersecurity-Skills
- [[analyzing-bootkit-and-rootkit-samples]] — Anthropic-Cybersecurity-Skills
