---
title: executing-active-directory-attack-simulation
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-active-directory-acl-abuse, conducting-internal-network-penetration-test, conducting-internal-reconnaissance-with-bloodhound-ce, executing-phishing-simulation-campaign, executing-red-team-exercise, exploiting-active-directory-with-bloodhound, implementing-continuous-security-validation-with-bas, mapping-attack-paths-with-bloodhound-ce, performing-active-directory-compromise-investigation, performing-active-directory-forest-trust-attack, performing-active-directory-vulnerability-assessment, performing-red-team-with-covenant, performing-vlan-hopping-attack]
confidence: medium
---

Executes authorized attack simulations against Active Directory environments to identify misconfigurations, weak credentials, dangerous privilege paths, and exploitable trust relationships that could lead to domain compromise. The tester uses BloodHound for attack path analysis, Mimikatz for credent

## Metadata

- **ID:** `executing-active-directory-attack-simulation`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/executing-active-directory-attack-simulation/SKILL.md`
- **Score:** 49.0
- **Edges:** 13

## Related Skills

- [[exploiting-active-directory-with-bloodhound]] *(complement)* — BloodHound is a graph-based Active Directory reconnaissance tool that uses graph theory to reveal hidden and unintended relationships within AD environments. Red teams use BloodHound to identify attac
- [[performing-active-directory-compromise-investigation]] *(complement)* — Investigate Active Directory compromise by analyzing authentication logs, replication metadata, Group Policy changes, and Kerberos ticket anomalies to identify attacker persistence and lateral movement paths.
- [[performing-active-directory-vulnerability-assessment]] *(complement)* — Assess Active Directory security posture using PingCastle, BloodHound, and Purple Knight to identify misconfigurations, privilege escalation paths, and attack vectors.
- [[mapping-attack-paths-with-bloodhound-ce]] *(similar)* — Collect Active Directory data with SharpHound and Entra ID data with AzureHound, ingest into BloodHound Community Edition, and analyze on-prem, cloud, and hybrid attack paths with built-in queries and custom Cypher.
- [[performing-active-directory-forest-trust-attack]] *(similar)* — Enumerate and audit Active Directory forest trust relationships using impacket for SID filtering analysis, trust key extraction, cross-forest SID history abuse detection, and inter-realm Kerberos ticket assessment.
- [[conducting-internal-reconnaissance-with-bloodhound-ce]] *(complement)* — Conduct internal Active Directory reconnaissance using BloodHound Community Edition to map attack paths, identify privilege escalation chains, and discover misconfigurations in domain environments.
- [[analyzing-active-directory-acl-abuse]] *(similar)* — Detect dangerous ACL misconfigurations in Active Directory using ldap3 to identify GenericAll, WriteDACL, and WriteOwner abuse paths
- [[conducting-internal-network-penetration-test]] *(similar)* — Execute an internal network penetration test simulating an insider threat or post-breach attacker to identify lateral movement paths, privilege escalation vectors, and sensitive data exposure within the corporate network.
- [[executing-phishing-simulation-campaign]] *(similar)* — Executes authorized phishing simulation campaigns to assess an organization's susceptibility to email-based social engineering attacks. The tester designs realistic phishing scenarios, builds credential harvesting infrastructure, sends targeted phishing emails, and tracks open rates, click-through r
- [[executing-red-team-exercise]] *(similar)* — Executes comprehensive red team exercises that simulate real-world adversary operations against an organization's people, processes, and technology. The red team operates with stealth as a primary objective, employing the full attack lifecycle from initial reconnaissance through objective completion
- [[implementing-continuous-security-validation-with-bas]] *(similar)* — Deploy Breach and Attack Simulation tools to continuously validate security control effectiveness by safely emulating real-world attack techniques across the kill chain.
- [[performing-red-team-with-covenant]] *(similar)* — Conduct red team operations using the Covenant C2 framework for authorized adversary simulation, including listener setup, grunt deployment, task execution, and lateral movement tracking.
- [[performing-vlan-hopping-attack]] *(similar)* — Simulates VLAN hopping attacks using switch spoofing and double tagging techniques in authorized environments to test VLAN segmentation effectiveness and validate switch port security configurations against Layer 2 bypass attacks.


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
