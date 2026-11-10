---
title: analyzing-bootkit-and-rootkit-samples
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-linux-elf-malware, analyzing-malware-persistence-with-autoruns, detecting-fileless-malware-techniques, detecting-process-injection-techniques, detecting-rootkit-activity, performing-firmware-malware-analysis, performing-malware-persistence-investigation, reverse-engineering-malware-with-ghidra]
confidence: medium
---

Analyzes bootkit and advanced rootkit malware that infects the Master Boot Record (MBR), Volume Boot Record (VBR), or UEFI firmware to gain persistence below the operating system. Covers boot sector analysis, UEFI module inspection, and anti-rootkit detection techniques. Activates for requests invol

## Metadata

- **ID:** `analyzing-bootkit-and-rootkit-samples`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/analyzing-bootkit-and-rootkit-samples/SKILL.md`
- **Score:** 48.0
- **Edges:** 8

## Related Skills

- [[performing-firmware-malware-analysis]] *(complement)* — Analyzes firmware images for embedded malware, backdoors, and unauthorized modifications targeting routers, IoT devices, UEFI/BIOS, and embedded systems. Covers firmware extraction, filesystem analysis, binary reverse engineering, and bootkit detection. Activates for requests involving firmware secu
- [[analyzing-linux-elf-malware]] *(similar)* — Analyzes malicious Linux ELF (Executable and Linkable Format) binaries including botnets, cryptominers, ransomware, and rootkits targeting Linux servers, containers, and cloud infrastructure. Covers static analysis, dynamic tracing, and reverse engineering of x86_64 and ARM ELF samples. Activates fo
- [[analyzing-malware-persistence-with-autoruns]] *(similar)* — Use Sysinternals Autoruns to systematically identify and analyze malware persistence mechanisms across registry keys, scheduled tasks, services, drivers, and startup locations on Windows systems.
- [[detecting-rootkit-activity]] *(similar)* — Detects rootkit presence on compromised systems by identifying hidden processes, hooked system calls, modified kernel structures, hidden files, and covert network connections using memory forensics, cross-view detection, and integrity checking techniques. Activates for requests involving rootkit det
- [[performing-malware-persistence-investigation]] *(similar)* — Systematically investigate all persistence mechanisms on Windows and Linux systems to identify how malware survives reboots and maintains access.
- [[detecting-fileless-malware-techniques]] *(similar)* — Detects and analyzes fileless malware that operates entirely in memory using PowerShell, WMI, .NET reflection, registry-resident payloads, and living-off-the-land binaries (LOLBins) without writing traditional executable files to disk. Activates for requests involving fileless threat detection, in-m
- [[detecting-process-injection-techniques]] *(similar)* — Detects and analyzes process injection techniques used by malware including classic DLL injection, process hollowing, APC injection, thread hijacking, and reflective loading. Uses memory forensics, API monitoring, and behavioral analysis to identify injection artifacts. Activates for requests involv
- [[reverse-engineering-malware-with-ghidra]] *(similar)* — Reverse engineers malware binaries using NSA's Ghidra disassembler and decompiler to understand internal logic, cryptographic routines, C2 protocols, and evasion techniques at the assembly and pseudo-C level. Activates for requests involving malware reverse engineering, disassembly analysis, decompi

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
- [[analyzing-campaign-attribution-evidence]] — Anthropic-Cybersecurity-Skills
