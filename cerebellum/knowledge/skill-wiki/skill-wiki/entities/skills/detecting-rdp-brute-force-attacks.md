---
title: detecting-rdp-brute-force-attacks
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-security-logs-with-splunk, configuring-windows-event-logging-for-detection, detecting-anomalous-authentication-patterns, detecting-credential-dumping-techniques, detecting-golden-ticket-forgery, detecting-kerberoasting-attacks, detecting-lateral-movement-with-zeek, detecting-mimikatz-execution-patterns, detecting-pass-the-hash-attacks, detecting-port-scanning-with-fail2ban, detecting-service-account-abuse, hunting-credential-stuffing-attacks, hunting-for-ntlm-relay-attacks]
confidence: low
---

Detect RDP brute force attacks by analyzing Windows Security Event Logs for failed authentication patterns (Event ID 4625), successful logons after failures (Event ID 4624), NLA failures, and source IP frequency analysis.

## Metadata

- **ID:** `detecting-rdp-brute-force-attacks`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-rdp-brute-force-attacks/SKILL.md`
- **Score:** 26.0
- **Edges:** 13

## Related Skills

- [[hunting-for-ntlm-relay-attacks]] *(complement)* — Detect NTLM relay attacks by analyzing Windows Event 4624 logon type 3 with NTLMSSP authentication, identifying IP-to-hostname mismatches, Responder traffic signatures, SMB signing status, and suspicious authentication patterns across the domain.
- [[analyzing-security-logs-with-splunk]] *(similar)* — Leverages Splunk Enterprise Security and SPL (Search Processing Language) to investigate security incidents through log correlation, timeline reconstruction, and anomaly detection. Covers Windows event logs, firewall logs, proxy logs, and authentication data analysis. Activates for requests involvin
- [[detecting-credential-dumping-techniques]] *(similar)* — Detect LSASS credential dumping, SAM database extraction, and NTDS.dit theft using Sysmon Event ID 10, Windows Security logs, and SIEM correlation rules
- [[detecting-lateral-movement-with-zeek]] *(similar)* — Detect lateral movement in network traffic using Zeek (formerly Bro) log analysis. Parses conn.log, smb_mapping.log, smb_files.log, dce_rpc.log, kerberos.log, and ntlm.log to identify SMB file transfers, NTLM account spray activity, remote service execution, and anomalous internal connections.

- [[detecting-service-account-abuse]] *(similar)* — Detect abuse of service accounts through anomalous interactive logons, privilege escalation, lateral movement, and unauthorized access patterns.
- [[detecting-pass-the-hash-attacks]] *(complement)* — Detect Pass-the-Hash attacks by analyzing NTLM authentication patterns, identifying Type 3 logons with NTLM where Kerberos is expected, and correlating with credential dumping.
- [[configuring-windows-event-logging-for-detection]] *(similar)* — Configures Windows Event Logging with advanced audit policies to generate high-fidelity security events for threat detection and forensic investigation. Use when enabling audit policies for logon events, process creation, privilege use, and object access to feed SIEM detection rules. Activates for r
- [[detecting-anomalous-authentication-patterns]] *(similar)* — Detects anomalous authentication patterns using UEBA analytics, statistical baselines, and machine learning models to identify impossible travel, credential stuffing, brute force, password spraying, and compromised account behaviors across authentication logs. Activates for requests involving authen
- [[detecting-golden-ticket-forgery]] *(similar)* — Detect Kerberos Golden Ticket forgery by analyzing Windows Event ID 4769 for RC4 encryption downgrades (0x17), abnormal ticket lifetimes, and krbtgt account anomalies in Splunk and Elastic SIEM
- [[detecting-kerberoasting-attacks]] *(similar)* — Detect Kerberoasting attacks by monitoring for anomalous Kerberos TGS requests targeting service accounts with SPNs for offline password cracking.
- [[detecting-mimikatz-execution-patterns]] *(similar)* — Detect Mimikatz execution through command-line patterns, LSASS access signatures, binary indicators, and in-memory detection of known modules.
- [[detecting-port-scanning-with-fail2ban]] *(similar)* — Configures Fail2ban with custom filters and actions to detect port scanning activity, SSH brute force attempts, and network reconnaissance, automatically banning offending IP addresses and alerting security teams to suspicious network probing.

- [[hunting-credential-stuffing-attacks]] *(similar)* — Detects credential stuffing attacks by analyzing authentication logs for login velocity anomalies, ASN diversity, password spray patterns, and geographic distribution of failed logins. Uses statistical analysis on Splunk or raw log data. Use when investigating account takeover campaigns or building 

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
