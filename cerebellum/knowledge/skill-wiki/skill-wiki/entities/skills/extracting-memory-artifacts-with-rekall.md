---
title: extracting-memory-artifacts-with-rekall
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-heap-spray-exploitation, analyzing-memory-dumps-with-volatility, investigating-ransomware-attack-artifacts]
confidence: low
---

Uses Rekall memory forensics framework to analyze memory dumps for process hollowing, injected code via VAD anomalies, hidden processes, and rootkit detection. Applies plugins like pslist, psscan, vadinfo, malfind, and dlllist to extract forensic artifacts from Windows memory images. Use during inci

## Metadata

- **ID:** `extracting-memory-artifacts-with-rekall`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/extracting-memory-artifacts-with-rekall/SKILL.md`
- **Score:** 30.0
- **Edges:** 3

## Related Skills

- [[investigating-ransomware-attack-artifacts]] *(similar)* — Identify, collect, and analyze ransomware attack artifacts to determine the variant, initial access vector, encryption scope, and recovery options.
- [[analyzing-memory-dumps-with-volatility]] *(complement)* — Analyzes RAM memory dumps from compromised systems using the Volatility framework to identify malicious processes, injected code, network connections, loaded modules, and extracted credentials. Supports Windows, Linux, and macOS memory forensics. Activates for requests involving memory forensics, RA
- [[analyzing-heap-spray-exploitation]] *(similar)* — Detect and analyze heap spray attacks in memory dumps using Volatility3 plugins to identify NOP sled patterns, shellcode landing zones, and suspicious large allocations in process virtual address space.

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
