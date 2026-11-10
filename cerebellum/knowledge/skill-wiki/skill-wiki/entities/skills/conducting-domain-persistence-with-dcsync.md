---
title: conducting-domain-persistence-with-dcsync
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [coercing-authentication-with-coercer-petitpotam, conducting-pass-the-ticket-attack, exploiting-constrained-delegation-abuse, exploiting-nopac-cve-2021-42278-42287, exploiting-zerologon-vulnerability-cve-2020-1472, hunting-for-dcsync-attacks, performing-active-directory-compromise-investigation, performing-active-directory-forest-trust-attack, performing-active-directory-vulnerability-assessment, performing-dns-enumeration-and-zone-transfer, performing-hash-cracking-with-hashcat, performing-lateral-movement-with-wmiexec, relaying-ntlm-for-adcs-esc8]
confidence: medium
---

Perform DCSync attacks to replicate Active Directory credentials and establish domain persistence by extracting KRBTGT, Domain Admin, and service account hashes for Golden Ticket creation.

## Metadata

- **ID:** `conducting-domain-persistence-with-dcsync`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/conducting-domain-persistence-with-dcsync/SKILL.md`
- **Score:** 46.0
- **Edges:** 13

## Related Skills

- [[performing-active-directory-compromise-investigation]] *(complement)* — Investigate Active Directory compromise by analyzing authentication logs, replication metadata, Group Policy changes, and Kerberos ticket anomalies to identify attacker persistence and lateral movement paths.
- [[performing-active-directory-forest-trust-attack]] *(complement)* — Enumerate and audit Active Directory forest trust relationships using impacket for SID filtering analysis, trust key extraction, cross-forest SID history abuse detection, and inter-realm Kerberos ticket assessment.
- [[conducting-pass-the-ticket-attack]] *(similar)* — Pass-the-Ticket (PtT) is a lateral movement technique that uses stolen Kerberos tickets (TGT or TGS) to authenticate to services without knowing the user's password. By extracting Kerberos tickets fro
- [[exploiting-constrained-delegation-abuse]] *(similar)* — Exploit Kerberos Constrained Delegation misconfigurations in Active Directory to impersonate privileged users via S4U2self and S4U2proxy extensions for lateral movement and privilege escalation.
- [[hunting-for-dcsync-attacks]] *(similar)* — Detect DCSync attacks by analyzing Windows Event ID 4662 for unauthorized DS-Replication-Get-Changes requests from non-domain-controller accounts.
- [[coercing-authentication-with-coercer-petitpotam]] *(similar)* — Trigger machine account authentication with PetitPotam (MS-EFSR) and Coercer across MS-RPRN, MS-DFSNM, and MS-FSRVP to feed NTLM relay into AD CS Web Enrollment (ESC8) and other relay targets.
- [[exploiting-nopac-cve-2021-42278-42287]] *(similar)* — Exploit the noPac vulnerability chain (CVE-2021-42278 sAMAccountName spoofing and CVE-2021-42287 KDC PAC confusion) to escalate from standard domain user to Domain Admin in Active Directory environments.
- [[exploiting-zerologon-vulnerability-cve-2020-1472]] *(similar)* — Exploit the Zerologon vulnerability (CVE-2020-1472) in the Netlogon Remote Protocol to achieve domain controller compromise by resetting the machine account password to empty.
- [[performing-active-directory-vulnerability-assessment]] *(similar)* — Assess Active Directory security posture using PingCastle, BloodHound, and Purple Knight to identify misconfigurations, privilege escalation paths, and attack vectors.
- [[performing-dns-enumeration-and-zone-transfer]] *(similar)* — Enumerates DNS records, attempts zone transfers, brute-forces subdomains, and maps DNS infrastructure during authorized reconnaissance to identify attack surface, misconfigurations, and information disclosure in target domains.

- [[performing-hash-cracking-with-hashcat]] *(similar)* — Hash cracking is an essential skill for penetration testers and security auditors to evaluate password strength. Hashcat is the world's fastest password recovery tool, supporting over 300 hash types w
- [[performing-lateral-movement-with-wmiexec]] *(similar)* — Perform lateral movement across Windows networks using WMI-based remote execution techniques including Impacket wmiexec.py, CrackMapExec, and native WMI commands for stealthy post-exploitation during red team engagements.
- [[relaying-ntlm-for-adcs-esc8]] *(similar)* — Run ntlmrelayx into ADCS web enrollment to obtain a domain controller certificate via ESC8.

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
