---
title: deploying-active-directory-honeytokens
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [deploying-honeytokens-and-canarytokens, deploying-ransomware-canary-files, detecting-azure-lateral-movement, detecting-credential-dumping-techniques, detecting-kerberoasting-attacks, detecting-pass-the-hash-attacks]
confidence: medium
---

Deploys deception-based honeytokens in Active Directory including fake privileged accounts with AdminCount=1, fake SPNs for Kerberoasting detection (honeyroasting), decoy GPOs with cpassword traps, and fake BloodHound paths. Monitors Windows Security Event IDs 4769, 4625, 4662, 5136 for honeytoken i

## Metadata

- **ID:** `deploying-active-directory-honeytokens`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/deploying-active-directory-honeytokens/SKILL.md`
- **Score:** 40.0
- **Edges:** 6

## Related Skills

- [[deploying-honeytokens-and-canarytokens]] *(similar)* — Plant canarytokens and honey credentials and alert on breach.
- [[detecting-azure-lateral-movement]] *(similar)* — Detect lateral movement in Azure AD/Entra ID environments using Microsoft Graph API audit logs, Azure Sentinel KQL hunting queries, and sign-in anomaly correlation to identify privilege escalation, token theft, and cross-tenant pivoting.
- [[detecting-credential-dumping-techniques]] *(similar)* — Detect LSASS credential dumping, SAM database extraction, and NTDS.dit theft using Sysmon Event ID 10, Windows Security logs, and SIEM correlation rules
- [[detecting-kerberoasting-attacks]] *(similar)* — Detect Kerberoasting attacks by monitoring for anomalous Kerberos TGS requests targeting service accounts with SPNs for offline password cracking.
- [[detecting-pass-the-hash-attacks]] *(similar)* — Detect Pass-the-Hash attacks by analyzing NTLM authentication patterns, identifying Type 3 logons with NTLM where Kerberos is expected, and correlating with credential dumping.
- [[deploying-ransomware-canary-files]] *(similar)* — Deploys and monitors ransomware canary files across critical directories using Python's watchdog library for real-time filesystem event detection. Places strategically named decoy files that mimic high-value targets (financial records, credentials, database exports) in locations ransomware typically

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
