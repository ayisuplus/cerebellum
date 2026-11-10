---
title: performing-active-directory-forest-trust-attack
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-active-directory-acl-abuse, auditing-entra-id-with-aadinternals, coercing-authentication-with-coercer-petitpotam, conducting-domain-persistence-with-dcsync, conducting-internal-reconnaissance-with-bloodhound-ce, conducting-pass-the-ticket-attack, executing-active-directory-attack-simulation, exploiting-active-directory-with-bloodhound, exploiting-adcs-with-certipy, exploiting-constrained-delegation-abuse, exploiting-nopac-cve-2021-42278-42287, hunting-for-t1098-account-manipulation, performing-active-directory-compromise-investigation, performing-active-directory-vulnerability-assessment, performing-dns-enumeration-and-zone-transfer, performing-lateral-movement-with-wmiexec, performing-subdomain-enumeration-with-subfinder, relaying-ntlm-for-adcs-esc8]
confidence: low
---

Enumerate and audit Active Directory forest trust relationships using impacket for SID filtering analysis, trust key extraction, cross-forest SID history abuse detection, and inter-realm Kerberos ticket assessment.

## Metadata

- **ID:** `performing-active-directory-forest-trust-attack`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/performing-active-directory-forest-trust-attack/SKILL.md`
- **Score:** 30.0
- **Edges:** 18

## Related Skills

- [[performing-active-directory-vulnerability-assessment]] *(complement)* — Assess Active Directory security posture using PingCastle, BloodHound, and Purple Knight to identify misconfigurations, privilege escalation paths, and attack vectors.
- [[analyzing-active-directory-acl-abuse]] *(similar)* — Detect dangerous ACL misconfigurations in Active Directory using ldap3 to identify GenericAll, WriteDACL, and WriteOwner abuse paths
- [[auditing-entra-id-with-aadinternals]] *(similar)* — Run Microsoft Entra ID tenant reconnaissance, token acquisition and manipulation, and federation backdoor testing with the AADInternals PowerShell toolkit to validate identity-attack resilience.
- [[conducting-internal-reconnaissance-with-bloodhound-ce]] *(similar)* — Conduct internal Active Directory reconnaissance using BloodHound Community Edition to map attack paths, identify privilege escalation chains, and discover misconfigurations in domain environments.
- [[exploiting-active-directory-with-bloodhound]] *(similar)* — BloodHound is a graph-based Active Directory reconnaissance tool that uses graph theory to reveal hidden and unintended relationships within AD environments. Red teams use BloodHound to identify attac
- [[conducting-domain-persistence-with-dcsync]] *(complement)* — Perform DCSync attacks to replicate Active Directory credentials and establish domain persistence by extracting KRBTGT, Domain Admin, and service account hashes for Golden Ticket creation.
- [[exploiting-constrained-delegation-abuse]] *(complement)* — Exploit Kerberos Constrained Delegation misconfigurations in Active Directory to impersonate privileged users via S4U2self and S4U2proxy extensions for lateral movement and privilege escalation.
- [[performing-active-directory-compromise-investigation]] *(complement)* — Investigate Active Directory compromise by analyzing authentication logs, replication metadata, Group Policy changes, and Kerberos ticket anomalies to identify attacker persistence and lateral movement paths.
- [[coercing-authentication-with-coercer-petitpotam]] *(similar)* — Trigger machine account authentication with PetitPotam (MS-EFSR) and Coercer across MS-RPRN, MS-DFSNM, and MS-FSRVP to feed NTLM relay into AD CS Web Enrollment (ESC8) and other relay targets.
- [[conducting-pass-the-ticket-attack]] *(similar)* — Pass-the-Ticket (PtT) is a lateral movement technique that uses stolen Kerberos tickets (TGT or TGS) to authenticate to services without knowing the user's password. By extracting Kerberos tickets fro
- [[executing-active-directory-attack-simulation]] *(similar)* — Executes authorized attack simulations against Active Directory environments to identify misconfigurations, weak credentials, dangerous privilege paths, and exploitable trust relationships that could lead to domain compromise. The tester uses BloodHound for attack path analysis, Mimikatz for credent
- [[exploiting-adcs-with-certipy]] *(similar)* — Enumerate and exploit Active Directory Certificate Services ESC1 through ESC16 misconfigurations with Certipy, including SAN abuse, NTLM relay to web enrollment (ESC8), and golden certificate forgery.
- [[exploiting-nopac-cve-2021-42278-42287]] *(similar)* — Exploit the noPac vulnerability chain (CVE-2021-42278 sAMAccountName spoofing and CVE-2021-42287 KDC PAC confusion) to escalate from standard domain user to Domain Admin in Active Directory environments.
- [[hunting-for-t1098-account-manipulation]] *(similar)* — Hunt for MITRE ATT&CK T1098 account manipulation including shadow admin creation, SID history injection, group membership changes, and credential modifications using Windows Security Event Logs.
- [[performing-dns-enumeration-and-zone-transfer]] *(similar)* — Enumerates DNS records, attempts zone transfers, brute-forces subdomains, and maps DNS infrastructure during authorized reconnaissance to identify attack surface, misconfigurations, and information disclosure in target domains.

- [[performing-lateral-movement-with-wmiexec]] *(similar)* — Perform lateral movement across Windows networks using WMI-based remote execution techniques including Impacket wmiexec.py, CrackMapExec, and native WMI commands for stealthy post-exploitation during red team engagements.
- [[performing-subdomain-enumeration-with-subfinder]] *(similar)* — Enumerate subdomains of target domains using ProjectDiscovery's Subfinder passive reconnaissance tool to map the attack surface during security assessments.
- [[relaying-ntlm-for-adcs-esc8]] *(similar)* — Run ntlmrelayx into ADCS web enrollment to obtain a domain controller certificate via ESC8.

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
