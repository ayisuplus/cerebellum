---
title: performing-privilege-escalation-on-linux
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [conducting-pass-the-ticket-attack, detecting-privilege-escalation-attempts, detecting-t1548-abuse-elevation-control-mechanism, escaping-containers-to-host, exploiting-active-directory-with-bloodhound, exploiting-aws-with-pacu, exploiting-constrained-delegation-abuse, exploiting-smb-vulnerabilities-with-metasploit, performing-active-directory-vulnerability-assessment, performing-binary-exploitation-analysis, performing-hash-cracking-with-hashcat, performing-lateral-movement-with-wmiexec]
confidence: low
---

Linux privilege escalation involves elevating from a low-privilege user account to root access on a compromised system. Red teams exploit misconfigurations, vulnerable services, kernel exploits, and w

## Metadata

- **ID:** `performing-privilege-escalation-on-linux`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/performing-privilege-escalation-on-linux/SKILL.md`
- **Score:** 23.0
- **Edges:** 12

## Related Skills

- [[exploiting-active-directory-with-bloodhound]] *(similar)* — BloodHound is a graph-based Active Directory reconnaissance tool that uses graph theory to reveal hidden and unintended relationships within AD environments. Red teams use BloodHound to identify attac
- [[exploiting-aws-with-pacu]] *(similar)* — Use Pacu modules for AWS privilege escalation, persistence, and backdooring.
- [[exploiting-constrained-delegation-abuse]] *(similar)* — Exploit Kerberos Constrained Delegation misconfigurations in Active Directory to impersonate privileged users via S4U2self and S4U2proxy extensions for lateral movement and privilege escalation.
- [[exploiting-smb-vulnerabilities-with-metasploit]] *(similar)* — Identifies and exploits SMB protocol vulnerabilities using Metasploit Framework during authorized penetration tests to demonstrate risks from unpatched Windows systems, misconfigured shares, and weak authentication in enterprise networks.

- [[performing-active-directory-vulnerability-assessment]] *(similar)* — Assess Active Directory security posture using PingCastle, BloodHound, and Purple Knight to identify misconfigurations, privilege escalation paths, and attack vectors.
- [[detecting-privilege-escalation-attempts]] *(complement)* — Detect privilege escalation attempts including token manipulation, UAC bypass, unquoted service paths, kernel exploits, and sudo/doas abuse across Windows and Linux.
- [[conducting-pass-the-ticket-attack]] *(similar)* — Pass-the-Ticket (PtT) is a lateral movement technique that uses stolen Kerberos tickets (TGT or TGS) to authenticate to services without knowing the user's password. By extracting Kerberos tickets fro
- [[detecting-t1548-abuse-elevation-control-mechanism]] *(similar)* — Detect abuse of elevation control mechanisms including UAC bypass, sudo exploitation, and setuid/setgid manipulation by monitoring registry modifications, process elevation flags, and unusual parent-child process relationships.
- [[escaping-containers-to-host]] *(similar)* — Exploit privileged pods, host mounts, runC CVEs, and exposed Docker sockets to break out of a container and reach the underlying host during authorized container-security assessments.
- [[performing-binary-exploitation-analysis]] *(similar)* — Analyze binary exploitation techniques including buffer overflows and ROP chains using pwntools Python library. Covers checksec analysis, gadget discovery with ROPgadget, and exploit development for CTF and authorized security assessments.

- [[performing-hash-cracking-with-hashcat]] *(similar)* — Hash cracking is an essential skill for penetration testers and security auditors to evaluate password strength. Hashcat is the world's fastest password recovery tool, supporting over 300 hash types w
- [[performing-lateral-movement-with-wmiexec]] *(similar)* — Perform lateral movement across Windows networks using WMI-based remote execution techniques including Impacket wmiexec.py, CrackMapExec, and native WMI commands for stealthy post-exploitation during red team engagements.

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
