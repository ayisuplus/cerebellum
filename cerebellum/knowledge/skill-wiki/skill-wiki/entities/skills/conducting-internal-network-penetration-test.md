---
title: conducting-internal-network-penetration-test
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [conducting-cloud-penetration-testing, conducting-full-scope-red-team-engagement, conducting-internal-reconnaissance-with-bloodhound-ce, conducting-mobile-app-penetration-test, conducting-network-penetration-test, conducting-pass-the-ticket-attack, conducting-spearphishing-simulation-campaign, conducting-wireless-network-penetration-test, configuring-network-segmentation-with-vlans, containing-active-breach, executing-active-directory-attack-simulation, executing-phishing-simulation-campaign, executing-red-team-exercise, implementing-continuous-security-validation-with-bas, implementing-network-deception-with-honeypots, performing-deception-technology-deployment, performing-gcp-penetration-testing-with-gcpbucketbrute, performing-kubernetes-penetration-testing, performing-lateral-movement-with-wmiexec, performing-physical-intrusion-assessment, performing-purple-team-exercise, performing-red-team-with-covenant, performing-thick-client-application-penetration-test, performing-threat-landscape-assessment-for-sector, performing-vlan-hopping-attack]
confidence: medium
---

Execute an internal network penetration test simulating an insider threat or post-breach attacker to identify lateral movement paths, privilege escalation vectors, and sensitive data exposure within the corporate network.

## Metadata

- **ID:** `conducting-internal-network-penetration-test`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/conducting-internal-network-penetration-test/SKILL.md`
- **Score:** 40.0
- **Edges:** 25

## Related Skills

- [[conducting-network-penetration-test]] *(complement)* — Conducts comprehensive network penetration tests against authorized target environments by performing host discovery, port scanning, service enumeration, vulnerability identification, and controlled exploitation to assess the security posture of network infrastructure. The tester follows PTES method
- [[conducting-internal-reconnaissance-with-bloodhound-ce]] *(similar)* — Conduct internal Active Directory reconnaissance using BloodHound Community Edition to map attack paths, identify privilege escalation chains, and discover misconfigurations in domain environments.
- [[conducting-wireless-network-penetration-test]] *(similar)* — Conducts authorized wireless network penetration tests to assess the security of WiFi infrastructure by testing for weak encryption protocols, captive portal bypasses, evil twin attacks, WPA2/WPA3 handshake capture, rogue access point detection, and client-side attacks. The tester evaluates wireless
- [[executing-active-directory-attack-simulation]] *(similar)* — Executes authorized attack simulations against Active Directory environments to identify misconfigurations, weak credentials, dangerous privilege paths, and exploitable trust relationships that could lead to domain compromise. The tester uses BloodHound for attack path analysis, Mimikatz for credent
- [[executing-red-team-exercise]] *(similar)* — Executes comprehensive red team exercises that simulate real-world adversary operations against an organization's people, processes, and technology. The red team operates with stealth as a primary objective, employing the full attack lifecycle from initial reconnaissance through objective completion
- [[conducting-cloud-penetration-testing]] *(similar)* — This skill outlines methodologies for performing authorized penetration testing against AWS, Azure, and GCP cloud environments. It covers understanding the shared responsibility model for testing scope, leveraging cloud-specific attack tools like Pacu and ScoutSuite, exploiting IAM misconfigurations
- [[conducting-full-scope-red-team-engagement]] *(similar)* — Plan and execute a comprehensive red team engagement covering reconnaissance through post-exploitation using MITRE ATT&CK-aligned TTPs to evaluate an organization's detection and response capabilities.
- [[conducting-mobile-app-penetration-test]] *(similar)* — Conducts penetration testing of iOS and Android mobile applications following the OWASP Mobile Application Security Testing Guide (MASTG) to identify vulnerabilities in data storage, network communication, authentication, cryptography, and platform-specific security controls. The tester performs sta
- [[conducting-pass-the-ticket-attack]] *(similar)* — Pass-the-Ticket (PtT) is a lateral movement technique that uses stolen Kerberos tickets (TGT or TGS) to authenticate to services without knowing the user's password. By extracting Kerberos tickets fro
- [[conducting-spearphishing-simulation-campaign]] *(similar)* — Spearphishing simulation is a targeted social engineering attack vector used by red teams to gain initial access. Unlike broad phishing campaigns, spearphishing uses OSINT-derived intelligence to craf
- [[configuring-network-segmentation-with-vlans]] *(similar)* — Designs and implements VLAN-based network segmentation on managed switches to isolate network zones, enforce access control between segments, and reduce the attack surface by limiting lateral movement paths in enterprise network environments.

- [[containing-active-breach]] *(similar)* — Executes containment strategies to stop active adversary operations and prevent lateral movement during a confirmed security breach. Implements short-term and long-term containment using network segmentation, endpoint isolation, credential revocation, and access control modifications. Activates for 
- [[executing-phishing-simulation-campaign]] *(similar)* — Executes authorized phishing simulation campaigns to assess an organization's susceptibility to email-based social engineering attacks. The tester designs realistic phishing scenarios, builds credential harvesting infrastructure, sends targeted phishing emails, and tracks open rates, click-through r
- [[implementing-continuous-security-validation-with-bas]] *(similar)* — Deploy Breach and Attack Simulation tools to continuously validate security control effectiveness by safely emulating real-world attack techniques across the kill chain.
- [[implementing-network-deception-with-honeypots]] *(similar)* — Deploy and manage network honeypots using OpenCanary, T-Pot, or Cowrie to detect unauthorized access, lateral movement, and attacker reconnaissance.
- [[performing-deception-technology-deployment]] *(similar)* — Deploys deception technology including honeypots, honeytokens, and decoy systems to detect attackers who have bypassed perimeter defenses, providing high-fidelity alerts with near-zero false positive rates. Use when SOC teams need early warning of lateral movement, credential abuse, or internal reco
- [[performing-gcp-penetration-testing-with-gcpbucketbrute]] *(similar)* — Perform GCP security testing using GCPBucketBrute for storage bucket enumeration, gcloud IAM privilege escalation path analysis, and service account permission auditing
- [[performing-kubernetes-penetration-testing]] *(similar)* — Kubernetes penetration testing systematically evaluates cluster security by simulating attacker techniques against the API server, kubelet, etcd, pods, RBAC, network policies, and secrets. Using tools
- [[performing-lateral-movement-with-wmiexec]] *(similar)* — Perform lateral movement across Windows networks using WMI-based remote execution techniques including Impacket wmiexec.py, CrackMapExec, and native WMI commands for stealthy post-exploitation during red team engagements.
- [[performing-physical-intrusion-assessment]] *(similar)* — Conduct authorized physical penetration testing using tailgating, badge cloning, lock bypassing, and rogue device deployment to evaluate facility security controls.
- [[performing-purple-team-exercise]] *(similar)* — Performs purple team exercises by coordinating red team adversary emulation with blue team detection validation using MITRE ATT&CK-mapped attack scenarios, real-time detection testing, and collaborative gap remediation. Use when SOC teams need to validate detection capabilities, improve analyst skil
- [[performing-red-team-with-covenant]] *(similar)* — Conduct red team operations using the Covenant C2 framework for authorized adversary simulation, including listener setup, grunt deployment, task execution, and lateral movement tracking.
- [[performing-thick-client-application-penetration-test]] *(similar)* — Conduct a thick client application penetration test to identify insecure local storage, hardcoded credentials, DLL hijacking, memory manipulation, and insecure API communication in desktop applications using dnSpy, Procmon, and Burp Suite.
- [[performing-threat-landscape-assessment-for-sector]] *(similar)* — Conduct a sector-specific threat landscape assessment by analyzing threat actor targeting patterns, common attack vectors, and industry-specific vulnerabilities to inform organizational risk management.
- [[performing-vlan-hopping-attack]] *(similar)* — Simulates VLAN hopping attacks using switch spoofing and double tagging techniques in authorized environments to test VLAN segmentation effectiveness and validate switch port security configurations against Layer 2 bypass attacks.


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
