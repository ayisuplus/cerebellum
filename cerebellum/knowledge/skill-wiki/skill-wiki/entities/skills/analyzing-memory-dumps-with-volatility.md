---
title: analyzing-memory-dumps-with-volatility
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-cyber-kill-chain, analyzing-heap-spray-exploitation, analyzing-macro-malware-in-office-documents, analyzing-network-covert-channels-in-malware, analyzing-pdf-malware-with-pdfid, analyzing-uefi-bootkit-persistence, deobfuscating-javascript-malware, detecting-secure-boot-bypass, extracting-memory-artifacts-with-rekall, investigating-ransomware-attack-artifacts, performing-sqlite-database-forensics]
confidence: medium
---

Analyzes RAM memory dumps from compromised systems using the Volatility framework to identify malicious processes, injected code, network connections, loaded modules, and extracted credentials. Supports Windows, Linux, and macOS memory forensics. Activates for requests involving memory forensics, RA

## Metadata

- **ID:** `analyzing-memory-dumps-with-volatility`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/analyzing-memory-dumps-with-volatility/SKILL.md`
- **Score:** 45.0
- **Edges:** 11

## Related Skills

- [[extracting-memory-artifacts-with-rekall]] *(complement)* — Uses Rekall memory forensics framework to analyze memory dumps for process hollowing, injected code via VAD anomalies, hidden processes, and rootkit detection. Applies plugins like pslist, psscan, vadinfo, malfind, and dlllist to extract forensic artifacts from Windows memory images. Use during inci
- [[analyzing-network-covert-channels-in-malware]] *(similar)* — Detect and analyze covert communication channels used by malware including DNS tunneling, ICMP exfiltration, steganographic HTTP, and protocol abuse for C2 and data exfiltration.
- [[analyzing-pdf-malware-with-pdfid]] *(similar)* — Analyzes malicious PDF files using PDFiD, pdf-parser, and peepdf to identify embedded JavaScript, shellcode, exploits, and suspicious objects without opening the document. Determines the attack vector and extracts embedded payloads for further analysis. Activates for requests involving PDF malware a
- [[investigating-ransomware-attack-artifacts]] *(similar)* — Identify, collect, and analyze ransomware attack artifacts to determine the variant, initial access vector, encryption scope, and recovery options.
- [[performing-sqlite-database-forensics]] *(similar)* — Perform forensic analysis of SQLite databases to recover deleted records from freelists and WAL files, decode encoded timestamps, and extract evidence from browser history, messaging apps, and mobile device databases.
- [[analyzing-heap-spray-exploitation]] *(complement)* — Detect and analyze heap spray attacks in memory dumps using Volatility3 plugins to identify NOP sled patterns, shellcode landing zones, and suspicious large allocations in process virtual address space.
- [[analyzing-cyber-kill-chain]] *(similar)* — Analyzes intrusion activity against the Lockheed Martin Cyber Kill Chain framework to identify which phases an adversary has completed, where defenses succeeded or failed, and what controls would have interrupted the attack at earlier phases. Use when conducting post-incident analysis, building prev
- [[analyzing-macro-malware-in-office-documents]] *(similar)* — Analyzes malicious VBA macros embedded in Microsoft Office documents (Word, Excel, PowerPoint) to identify download cradles, payload execution, persistence mechanisms, and anti-analysis techniques. Uses olevba, oledump, and VBA deobfuscation to extract the attack chain. Activates for requests involv
- [[analyzing-uefi-bootkit-persistence]] *(similar)* — Analyzes UEFI bootkit persistence mechanisms including firmware implants in SPI flash, EFI System Partition (ESP) modifications, Secure Boot bypass techniques, and UEFI variable manipulation. Covers detection of known bootkit families (BlackLotus, LoJax, MosaicRegressor, MoonBounce, CosmicStrand), E
- [[deobfuscating-javascript-malware]] *(similar)* — Deobfuscates malicious JavaScript code used in web-based attacks, phishing pages, and dropper scripts by reversing encoding layers, eval chains, string manipulation, and control flow obfuscation to reveal the original malicious logic. Activates for requests involving JavaScript malware analysis, scr
- [[detecting-secure-boot-bypass]] *(similar)* — Detect bootkits such as BlackLotus and Bootkitty and Secure Boot bypass via DBX and binary checks.

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
