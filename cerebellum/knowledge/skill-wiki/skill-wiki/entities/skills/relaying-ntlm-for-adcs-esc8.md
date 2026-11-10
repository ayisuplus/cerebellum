---
title: relaying-ntlm-for-adcs-esc8
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [coercing-authentication-with-coercer-petitpotam, conducting-domain-persistence-with-dcsync, exploiting-adcs-with-certipy, exploiting-constrained-delegation-abuse, exploiting-nopac-cve-2021-42278-42287, exploiting-zerologon-vulnerability-cve-2020-1472, performing-active-directory-forest-trust-attack]
confidence: medium
---

Run ntlmrelayx into ADCS web enrollment to obtain a domain controller certificate via ESC8.

## Metadata

- **ID:** `relaying-ntlm-for-adcs-esc8`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/relaying-ntlm-for-adcs-esc8/SKILL.md`
- **Score:** 42.0
- **Edges:** 7

## Related Skills

- [[conducting-domain-persistence-with-dcsync]] *(similar)* — Perform DCSync attacks to replicate Active Directory credentials and establish domain persistence by extracting KRBTGT, Domain Admin, and service account hashes for Golden Ticket creation.
- [[exploiting-constrained-delegation-abuse]] *(similar)* — Exploit Kerberos Constrained Delegation misconfigurations in Active Directory to impersonate privileged users via S4U2self and S4U2proxy extensions for lateral movement and privilege escalation.
- [[exploiting-nopac-cve-2021-42278-42287]] *(similar)* — Exploit the noPac vulnerability chain (CVE-2021-42278 sAMAccountName spoofing and CVE-2021-42287 KDC PAC confusion) to escalate from standard domain user to Domain Admin in Active Directory environments.
- [[exploiting-zerologon-vulnerability-cve-2020-1472]] *(similar)* — Exploit the Zerologon vulnerability (CVE-2020-1472) in the Netlogon Remote Protocol to achieve domain controller compromise by resetting the machine account password to empty.
- [[performing-active-directory-forest-trust-attack]] *(similar)* — Enumerate and audit Active Directory forest trust relationships using impacket for SID filtering analysis, trust key extraction, cross-forest SID history abuse detection, and inter-realm Kerberos ticket assessment.
- [[coercing-authentication-with-coercer-petitpotam]] *(complement)* — Trigger machine account authentication with PetitPotam (MS-EFSR) and Coercer across MS-RPRN, MS-DFSNM, and MS-FSRVP to feed NTLM relay into AD CS Web Enrollment (ESC8) and other relay targets.
- [[exploiting-adcs-with-certipy]] *(complement)* — Enumerate and exploit Active Directory Certificate Services ESC1 through ESC16 misconfigurations with Certipy, including SAN abuse, NTLM relay to web enrollment (ESC8), and golden certificate forgery.

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
