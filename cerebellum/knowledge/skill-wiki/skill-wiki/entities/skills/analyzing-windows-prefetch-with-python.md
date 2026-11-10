---
title: analyzing-windows-prefetch-with-python
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-cobaltstrike-malleable-c2-profiles, analyzing-malware-family-relationships-with-malpedia, analyzing-network-flow-data-with-netflow, analyzing-powershell-script-block-logging, analyzing-typosquatting-domains-with-dnstwist, analyzing-usb-device-connection-history, analyzing-windows-shellbag-artifacts, building-attack-pattern-library-from-cti-reports, building-super-timelines-with-plaso, detecting-living-off-the-land-attacks, detecting-mimikatz-execution-patterns, extracting-windows-event-logs-artifacts, hunting-for-startup-folder-persistence, performing-firmware-extraction-with-binwalk]
confidence: medium
---

Parse Windows Prefetch files using the windowsprefetch Python library to reconstruct application execution history, detect renamed or masquerading binaries, and identify suspicious program execution patterns.

## Metadata

- **ID:** `analyzing-windows-prefetch-with-python`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/analyzing-windows-prefetch-with-python/SKILL.md`
- **Score:** 44.0
- **Edges:** 14

## Related Skills

- [[analyzing-network-flow-data-with-netflow]] *(similar)* — Parse NetFlow v9 and IPFIX records to detect volumetric anomalies, port scanning, data exfiltration, and C2 beaconing patterns. Uses the Python netflow library to decode flow records, builds traffic baselines, and applies statistical analysis to identify flows with abnormal byte counts, connection d
- [[analyzing-windows-shellbag-artifacts]] *(similar)* — Analyze Windows Shellbag registry artifacts to reconstruct folder browsing activity, detect access to removable media and network shares, and establish user interaction with directories even after deletion using SBECmd and ShellBags Explorer.
- [[detecting-living-off-the-land-attacks]] *(similar)* — Detect abuse of legitimate Windows binaries (LOLBins) used for living off the land attacks. Monitors process creation, command-line arguments, and parent-child relationships to identify suspicious LOLBin execution patterns.

- [[detecting-mimikatz-execution-patterns]] *(similar)* — Detect Mimikatz execution through command-line patterns, LSASS access signatures, binary indicators, and in-memory detection of known modules.
- [[extracting-windows-event-logs-artifacts]] *(similar)* — Extract, parse, and analyze Windows Event Logs (EVTX) using Chainsaw, Hayabusa, and EvtxECmd to detect lateral movement, persistence, and privilege escalation.
- [[analyzing-powershell-script-block-logging]] *(complement)* — Parse Windows PowerShell Script Block Logs (Event ID 4104) from EVTX files to detect obfuscated commands, encoded payloads, and living-off-the-land techniques. Uses python-evtx to extract and reconstruct multi-block scripts, applies entropy analysis and pattern matching for Base64-encoded commands, 
- [[analyzing-cobaltstrike-malleable-c2-profiles]] *(similar)* — Parse and analyze Cobalt Strike Malleable C2 profiles using dissect.cobaltstrike and pyMalleableC2 to extract C2 indicators, detect evasion techniques, and generate network detection signatures.
- [[analyzing-malware-family-relationships-with-malpedia]] *(similar)* — Use the Malpedia platform and API to research malware family relationships, track variant evolution, link families to threat actors, and integrate YARA rules for detection across malware lineages.
- [[analyzing-typosquatting-domains-with-dnstwist]] *(similar)* — Detect typosquatting, homograph phishing, and brand impersonation domains using dnstwist to generate domain permutations and identify registered lookalike domains targeting your organization.
- [[analyzing-usb-device-connection-history]] *(similar)* — Investigate USB device connection history from Windows registry, event logs, and setupapi logs to track removable media usage and potential data exfiltration.
- [[building-attack-pattern-library-from-cti-reports]] *(similar)* — Extract and catalog attack patterns from cyber threat intelligence reports into a structured STIX-based library mapped to MITRE ATT&CK for detection engineering and threat-informed defense.
- [[building-super-timelines-with-plaso]] *(similar)* — Generate log2timeline and Plaso super-timelines and triage them in Timesketch.
- [[hunting-for-startup-folder-persistence]] *(similar)* — Detect T1547.001 startup folder persistence by monitoring Windows startup directories for suspicious file creation, analyzing autoruns entries, and using Python watchdog for real-time filesystem monitoring.
- [[performing-firmware-extraction-with-binwalk]] *(similar)* — Performs firmware image extraction and analysis using binwalk to identify embedded filesystems, compressed archives, bootloaders, kernel images, and cryptographic material. Covers entropy analysis for detecting encrypted or compressed regions, recursive extraction of nested archives, SquashFS/CramFS

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
