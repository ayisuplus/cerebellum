---
title: detecting-process-injection-techniques
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-bootkit-and-rootkit-samples, analyzing-malware-behavior-with-cuckoo-sandbox, analyzing-malware-persistence-with-autoruns, analyzing-malware-sandbox-evasion-techniques, detecting-fileless-malware-techniques, detecting-rootkit-activity, performing-dynamic-analysis-with-any-run, reverse-engineering-dotnet-malware-with-dnspy]
confidence: medium
---

Detects and analyzes process injection techniques used by malware including classic DLL injection, process hollowing, APC injection, thread hijacking, and reflective loading. Uses memory forensics, API monitoring, and behavioral analysis to identify injection artifacts. Activates for requests involv

## Metadata

- **ID:** `detecting-process-injection-techniques`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-process-injection-techniques/SKILL.md`
- **Score:** 48.0
- **Edges:** 8

## Related Skills

- [[detecting-rootkit-activity]] *(complement)* — Detects rootkit presence on compromised systems by identifying hidden processes, hooked system calls, modified kernel structures, hidden files, and covert network connections using memory forensics, cross-view detection, and integrity checking techniques. Activates for requests involving rootkit det
- [[analyzing-bootkit-and-rootkit-samples]] *(similar)* — Analyzes bootkit and advanced rootkit malware that infects the Master Boot Record (MBR), Volume Boot Record (VBR), or UEFI firmware to gain persistence below the operating system. Covers boot sector analysis, UEFI module inspection, and anti-rootkit detection techniques. Activates for requests invol
- [[analyzing-malware-behavior-with-cuckoo-sandbox]] *(similar)* — Executes malware samples in Cuckoo Sandbox to observe runtime behavior including process creation, file system modifications, registry changes, network communications, and API calls. Generates comprehensive behavioral reports for malware classification and IOC extraction. Activates for requests invo
- [[performing-dynamic-analysis-with-any-run]] *(similar)* — Performs interactive dynamic malware analysis using the ANY.RUN cloud sandbox to observe real-time execution behavior, interact with malware prompts, and capture process trees, network traffic, and system changes. Activates for requests involving interactive sandbox analysis, cloud-based malware det
- [[reverse-engineering-dotnet-malware-with-dnspy]] *(similar)* — Reverse engineers .NET malware using dnSpy decompiler and debugger to analyze C#/VB.NET source code, identify obfuscation techniques, extract configurations, and understand malicious functionality including stealers, RATs, and loaders. Activates for requests involving .NET malware analysis, C# malwa
- [[detecting-fileless-malware-techniques]] *(complement)* — Detects and analyzes fileless malware that operates entirely in memory using PowerShell, WMI, .NET reflection, registry-resident payloads, and living-off-the-land binaries (LOLBins) without writing traditional executable files to disk. Activates for requests involving fileless threat detection, in-m
- [[analyzing-malware-persistence-with-autoruns]] *(similar)* — Use Sysinternals Autoruns to systematically identify and analyze malware persistence mechanisms across registry keys, scheduled tasks, services, drivers, and startup locations on Windows systems.
- [[analyzing-malware-sandbox-evasion-techniques]] *(similar)* — Detect sandbox evasion techniques in malware samples by analyzing timing checks, VM artifact queries, user interaction detection, and sleep inflation patterns from Cuckoo/AnyRun behavioral reports

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
