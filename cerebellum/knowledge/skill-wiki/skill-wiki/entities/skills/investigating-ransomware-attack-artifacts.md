---
title: investigating-ransomware-attack-artifacts
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-cyber-kill-chain, analyzing-heap-spray-exploitation, analyzing-macro-malware-in-office-documents, analyzing-memory-dumps-with-volatility, analyzing-network-covert-channels-in-malware, analyzing-pdf-malware-with-pdfid, analyzing-threat-actor-ttps-with-mitre-attack, analyzing-uefi-bootkit-persistence, collecting-open-source-intelligence, eradicating-malware-from-infected-systems, extracting-memory-artifacts-with-rekall, hunting-for-data-exfiltration-indicators, hunting-for-dcsync-attacks, implementing-anti-ransomware-group-policy, performing-active-directory-compromise-investigation, testing-ransomware-recovery-procedures]
confidence: medium
---

Identify, collect, and analyze ransomware attack artifacts to determine the variant, initial access vector, encryption scope, and recovery options.

## Metadata

- **ID:** `investigating-ransomware-attack-artifacts`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/investigating-ransomware-attack-artifacts/SKILL.md`
- **Score:** 51.0
- **Edges:** 16

## Related Skills

- [[analyzing-threat-actor-ttps-with-mitre-attack]] *(similar)* — MITRE ATT&CK is a globally-accessible knowledge base of adversary tactics, techniques, and procedures (TTPs) based on real-world observations. This skill covers systematically mapping threat actor beh
- [[collecting-open-source-intelligence]] *(similar)* — Collects and synthesizes open-source intelligence (OSINT) about threat actors, malicious infrastructure, and attack campaigns using publicly available data sources, passive reconnaissance tools, and dark web monitoring. Use when investigating external threat actor infrastructure, performing pre-enga
- [[hunting-for-data-exfiltration-indicators]] *(similar)* — Hunt for data exfiltration through network traffic analysis, detecting unusual data flows, DNS tunneling, cloud storage uploads, and encrypted channel abuse.
- [[hunting-for-dcsync-attacks]] *(similar)* — Detect DCSync attacks by analyzing Windows Event ID 4662 for unauthorized DS-Replication-Get-Changes requests from non-domain-controller accounts.
- [[performing-active-directory-compromise-investigation]] *(similar)* — Investigate Active Directory compromise by analyzing authentication logs, replication metadata, Group Policy changes, and Kerberos ticket anomalies to identify attacker persistence and lateral movement paths.
- [[analyzing-cyber-kill-chain]] *(similar)* — Analyzes intrusion activity against the Lockheed Martin Cyber Kill Chain framework to identify which phases an adversary has completed, where defenses succeeded or failed, and what controls would have interrupted the attack at earlier phases. Use when conducting post-incident analysis, building prev
- [[analyzing-heap-spray-exploitation]] *(similar)* — Detect and analyze heap spray attacks in memory dumps using Volatility3 plugins to identify NOP sled patterns, shellcode landing zones, and suspicious large allocations in process virtual address space.
- [[analyzing-macro-malware-in-office-documents]] *(similar)* — Analyzes malicious VBA macros embedded in Microsoft Office documents (Word, Excel, PowerPoint) to identify download cradles, payload execution, persistence mechanisms, and anti-analysis techniques. Uses olevba, oledump, and VBA deobfuscation to extract the attack chain. Activates for requests involv
- [[analyzing-memory-dumps-with-volatility]] *(similar)* — Analyzes RAM memory dumps from compromised systems using the Volatility framework to identify malicious processes, injected code, network connections, loaded modules, and extracted credentials. Supports Windows, Linux, and macOS memory forensics. Activates for requests involving memory forensics, RA
- [[analyzing-network-covert-channels-in-malware]] *(similar)* — Detect and analyze covert communication channels used by malware including DNS tunneling, ICMP exfiltration, steganographic HTTP, and protocol abuse for C2 and data exfiltration.
- [[analyzing-pdf-malware-with-pdfid]] *(similar)* — Analyzes malicious PDF files using PDFiD, pdf-parser, and peepdf to identify embedded JavaScript, shellcode, exploits, and suspicious objects without opening the document. Determines the attack vector and extracts embedded payloads for further analysis. Activates for requests involving PDF malware a
- [[analyzing-uefi-bootkit-persistence]] *(similar)* — Analyzes UEFI bootkit persistence mechanisms including firmware implants in SPI flash, EFI System Partition (ESP) modifications, Secure Boot bypass techniques, and UEFI variable manipulation. Covers detection of known bootkit families (BlackLotus, LoJax, MosaicRegressor, MoonBounce, CosmicStrand), E
- [[eradicating-malware-from-infected-systems]] *(similar)* — Systematically remove malware, backdoors, and attacker persistence mechanisms from infected systems while ensuring complete eradication and preventing re-infection.
- [[extracting-memory-artifacts-with-rekall]] *(similar)* — Uses Rekall memory forensics framework to analyze memory dumps for process hollowing, injected code via VAD anomalies, hidden processes, and rootkit detection. Applies plugins like pslist, psscan, vadinfo, malfind, and dlllist to extract forensic artifacts from Windows memory images. Use during inci
- [[implementing-anti-ransomware-group-policy]] *(similar)* — Configures Windows Group Policy Objects (GPO) to prevent ransomware execution and limit its spread. Implements AppLocker rules, Software Restriction Policies, Controlled Folder Access, attack surface reduction rules, and network protection settings. Activates for requests involving Windows GPO harde
- [[testing-ransomware-recovery-procedures]] *(similar)* — Test and validate ransomware recovery procedures including backup restore operations, RTO/RPO target verification, recovery sequencing, and clean restore validation to ensure organizational resilience against destructive ransomware attacks.

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
