---
title: performing-active-directory-compromise-investigation
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-active-directory-acl-abuse, auditing-entra-id-with-aadinternals, conducting-domain-persistence-with-dcsync, conducting-internal-reconnaissance-with-bloodhound-ce, conducting-pass-the-ticket-attack, detecting-azure-service-principal-abuse, detecting-compromised-cloud-credentials, eradicating-malware-from-infected-systems, executing-active-directory-attack-simulation, exploiting-active-directory-with-bloodhound, exploiting-adcs-with-certipy, exploiting-constrained-delegation-abuse, exploiting-zerologon-vulnerability-cve-2020-1472, hunting-for-dcsync-attacks, hunting-for-suspicious-scheduled-tasks, hunting-for-t1098-account-manipulation, investigating-ransomware-attack-artifacts, mapping-attack-paths-with-bloodhound-ce, performing-active-directory-forest-trust-attack, performing-active-directory-vulnerability-assessment, performing-credential-access-with-lazagne, performing-lateral-movement-with-wmiexec, post-exploiting-microsoft-graph-with-graphrunner]
confidence: medium
---

Investigate Active Directory compromise by analyzing authentication logs, replication metadata, Group Policy changes, and Kerberos ticket anomalies to identify attacker persistence and lateral movement paths.

## Metadata

- **ID:** `performing-active-directory-compromise-investigation`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/performing-active-directory-compromise-investigation/SKILL.md`
- **Score:** 45.0
- **Edges:** 23

## Related Skills

- [[performing-active-directory-forest-trust-attack]] *(complement)* — Enumerate and audit Active Directory forest trust relationships using impacket for SID filtering analysis, trust key extraction, cross-forest SID history abuse detection, and inter-realm Kerberos ticket assessment.
- [[performing-active-directory-vulnerability-assessment]] *(complement)* — Assess Active Directory security posture using PingCastle, BloodHound, and Purple Knight to identify misconfigurations, privilege escalation paths, and attack vectors.
- [[detecting-azure-service-principal-abuse]] *(similar)* — Detect and investigate Azure service principal abuse including privilege escalation, credential compromise, admin consent bypass, and unauthorized enumeration in Microsoft Entra ID environments.
- [[exploiting-adcs-with-certipy]] *(similar)* — Enumerate and exploit Active Directory Certificate Services ESC1 through ESC16 misconfigurations with Certipy, including SAN abuse, NTLM relay to web enrollment (ESC8), and golden certificate forgery.
- [[performing-lateral-movement-with-wmiexec]] *(similar)* — Perform lateral movement across Windows networks using WMI-based remote execution techniques including Impacket wmiexec.py, CrackMapExec, and native WMI commands for stealthy post-exploitation during red team engagements.
- [[conducting-domain-persistence-with-dcsync]] *(complement)* — Perform DCSync attacks to replicate Active Directory credentials and establish domain persistence by extracting KRBTGT, Domain Admin, and service account hashes for Golden Ticket creation.
- [[executing-active-directory-attack-simulation]] *(complement)* — Executes authorized attack simulations against Active Directory environments to identify misconfigurations, weak credentials, dangerous privilege paths, and exploitable trust relationships that could lead to domain compromise. The tester uses BloodHound for attack path analysis, Mimikatz for credent
- [[analyzing-active-directory-acl-abuse]] *(similar)* — Detect dangerous ACL misconfigurations in Active Directory using ldap3 to identify GenericAll, WriteDACL, and WriteOwner abuse paths
- [[auditing-entra-id-with-aadinternals]] *(similar)* — Run Microsoft Entra ID tenant reconnaissance, token acquisition and manipulation, and federation backdoor testing with the AADInternals PowerShell toolkit to validate identity-attack resilience.
- [[conducting-internal-reconnaissance-with-bloodhound-ce]] *(similar)* — Conduct internal Active Directory reconnaissance using BloodHound Community Edition to map attack paths, identify privilege escalation chains, and discover misconfigurations in domain environments.
- [[conducting-pass-the-ticket-attack]] *(similar)* — Pass-the-Ticket (PtT) is a lateral movement technique that uses stolen Kerberos tickets (TGT or TGS) to authenticate to services without knowing the user's password. By extracting Kerberos tickets fro
- [[detecting-compromised-cloud-credentials]] *(similar)* — Detecting compromised cloud credentials across AWS, Azure, and GCP by analyzing anomalous API activity, impossible travel patterns, unauthorized resource provisioning, and credential abuse indicators using GuardDuty, Defender for Identity, and SCC Event Threat Detection.

- [[eradicating-malware-from-infected-systems]] *(similar)* — Systematically remove malware, backdoors, and attacker persistence mechanisms from infected systems while ensuring complete eradication and preventing re-infection.
- [[exploiting-active-directory-with-bloodhound]] *(similar)* — BloodHound is a graph-based Active Directory reconnaissance tool that uses graph theory to reveal hidden and unintended relationships within AD environments. Red teams use BloodHound to identify attac
- [[exploiting-constrained-delegation-abuse]] *(similar)* — Exploit Kerberos Constrained Delegation misconfigurations in Active Directory to impersonate privileged users via S4U2self and S4U2proxy extensions for lateral movement and privilege escalation.
- [[exploiting-zerologon-vulnerability-cve-2020-1472]] *(similar)* — Exploit the Zerologon vulnerability (CVE-2020-1472) in the Netlogon Remote Protocol to achieve domain controller compromise by resetting the machine account password to empty.
- [[hunting-for-dcsync-attacks]] *(similar)* — Detect DCSync attacks by analyzing Windows Event ID 4662 for unauthorized DS-Replication-Get-Changes requests from non-domain-controller accounts.
- [[hunting-for-suspicious-scheduled-tasks]] *(similar)* — Hunt for adversary persistence and execution via Windows scheduled tasks by analyzing task creation events, suspicious task properties, and unusual execution patterns that indicate T1053.005 abuse.
- [[hunting-for-t1098-account-manipulation]] *(similar)* — Hunt for MITRE ATT&CK T1098 account manipulation including shadow admin creation, SID history injection, group membership changes, and credential modifications using Windows Security Event Logs.
- [[investigating-ransomware-attack-artifacts]] *(similar)* — Identify, collect, and analyze ransomware attack artifacts to determine the variant, initial access vector, encryption scope, and recovery options.
- [[mapping-attack-paths-with-bloodhound-ce]] *(similar)* — Collect Active Directory data with SharpHound and Entra ID data with AzureHound, ingest into BloodHound Community Edition, and analyze on-prem, cloud, and hybrid attack paths with built-in queries and custom Cypher.
- [[performing-credential-access-with-lazagne]] *(similar)* — Extract stored credentials from compromised endpoints using the LaZagne post-exploitation tool to recover passwords from browsers, databases, system vaults, and applications during authorized red team operations.
- [[post-exploiting-microsoft-graph-with-graphrunner]] *(similar)* — Perform recon, persistence, privilege escalation, and data search via the Microsoft Graph API using GraphRunner.

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
