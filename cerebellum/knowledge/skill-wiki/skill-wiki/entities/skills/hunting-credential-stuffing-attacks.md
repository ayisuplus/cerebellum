---
title: hunting-credential-stuffing-attacks
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [detecting-anomalous-authentication-patterns, detecting-kerberoasting-attacks, detecting-pass-the-hash-attacks, detecting-rdp-brute-force-attacks, detecting-service-account-abuse, hunting-for-ntlm-relay-attacks, hunting-for-spearphishing-indicators]
confidence: low
---

Detects credential stuffing attacks by analyzing authentication logs for login velocity anomalies, ASN diversity, password spray patterns, and geographic distribution of failed logins. Uses statistical analysis on Splunk or raw log data. Use when investigating account takeover campaigns or building

## Metadata

- **ID:** `hunting-credential-stuffing-attacks`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/hunting-credential-stuffing-attacks/SKILL.md`
- **Score:** 30.0
- **Edges:** 7

## Related Skills

- [[detecting-kerberoasting-attacks]] *(similar)* — Detect Kerberoasting attacks by monitoring for anomalous Kerberos TGS requests targeting service accounts with SPNs for offline password cracking.
- [[detecting-pass-the-hash-attacks]] *(similar)* — Detect Pass-the-Hash attacks by analyzing NTLM authentication patterns, identifying Type 3 logons with NTLM where Kerberos is expected, and correlating with credential dumping.
- [[detecting-rdp-brute-force-attacks]] *(similar)* — Detect RDP brute force attacks by analyzing Windows Security Event Logs for failed authentication patterns (Event ID 4625), successful logons after failures (Event ID 4624), NLA failures, and source IP frequency analysis.
- [[hunting-for-ntlm-relay-attacks]] *(similar)* — Detect NTLM relay attacks by analyzing Windows Event 4624 logon type 3 with NTLMSSP authentication, identifying IP-to-hostname mismatches, Responder traffic signatures, SMB signing status, and suspicious authentication patterns across the domain.
- [[hunting-for-spearphishing-indicators]] *(similar)* — Hunt for spearphishing campaign indicators across email logs, endpoint telemetry, and network data to detect targeted email attacks.
- [[detecting-anomalous-authentication-patterns]] *(complement)* — Detects anomalous authentication patterns using UEBA analytics, statistical baselines, and machine learning models to identify impossible travel, credential stuffing, brute force, password spraying, and compromised account behaviors across authentication logs. Activates for requests involving authen
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
- [[analyzing-azure-activity-logs-for-threats]] — Anthropic-Cybersecurity-Skills
- [[analyzing-bootkit-and-rootkit-samples]] — Anthropic-Cybersecurity-Skills
