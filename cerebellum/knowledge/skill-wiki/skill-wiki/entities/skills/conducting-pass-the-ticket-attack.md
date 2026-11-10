---
title: conducting-pass-the-ticket-attack
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [conducting-domain-persistence-with-dcsync, conducting-internal-network-penetration-test, exploiting-constrained-delegation-abuse, performing-active-directory-compromise-investigation, performing-active-directory-forest-trust-attack, performing-privilege-escalation-on-linux]
confidence: low
---

Pass-the-Ticket (PtT) is a lateral movement technique that uses stolen Kerberos tickets (TGT or TGS) to authenticate to services without knowing the user's password. By extracting Kerberos tickets fro

## Metadata

- **ID:** `conducting-pass-the-ticket-attack`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/conducting-pass-the-ticket-attack/SKILL.md`
- **Score:** 35.0
- **Edges:** 6

## Related Skills

- [[conducting-internal-network-penetration-test]] *(similar)* — Execute an internal network penetration test simulating an insider threat or post-breach attacker to identify lateral movement paths, privilege escalation vectors, and sensitive data exposure within the corporate network.
- [[exploiting-constrained-delegation-abuse]] *(similar)* — Exploit Kerberos Constrained Delegation misconfigurations in Active Directory to impersonate privileged users via S4U2self and S4U2proxy extensions for lateral movement and privilege escalation.
- [[performing-active-directory-compromise-investigation]] *(similar)* — Investigate Active Directory compromise by analyzing authentication logs, replication metadata, Group Policy changes, and Kerberos ticket anomalies to identify attacker persistence and lateral movement paths.
- [[performing-active-directory-forest-trust-attack]] *(similar)* — Enumerate and audit Active Directory forest trust relationships using impacket for SID filtering analysis, trust key extraction, cross-forest SID history abuse detection, and inter-realm Kerberos ticket assessment.
- [[performing-privilege-escalation-on-linux]] *(similar)* — Linux privilege escalation involves elevating from a low-privilege user account to root access on a compromised system. Red teams exploit misconfigurations, vulnerable services, kernel exploits, and w
- [[conducting-domain-persistence-with-dcsync]] *(similar)* — Perform DCSync attacks to replicate Active Directory credentials and establish domain persistence by extracting KRBTGT, Domain Admin, and service account hashes for Golden Ticket creation.

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
