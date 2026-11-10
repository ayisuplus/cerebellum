---
title: detecting-rootkit-activity
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-bootkit-and-rootkit-samples, analyzing-docker-container-forensics, analyzing-malware-persistence-with-autoruns, detecting-fileless-malware-techniques, detecting-process-injection-techniques, performing-endpoint-forensics-investigation, performing-firmware-malware-analysis, performing-malware-persistence-investigation]
confidence: medium
---

Detects rootkit presence on compromised systems by identifying hidden processes, hooked system calls, modified kernel structures, hidden files, and covert network connections using memory forensics, cross-view detection, and integrity checking techniques. Activates for requests involving rootkit det

## Metadata

- **ID:** `detecting-rootkit-activity`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-rootkit-activity/SKILL.md`
- **Score:** 45.0
- **Edges:** 8

## Related Skills

- [[analyzing-docker-container-forensics]] *(similar)* — Investigate compromised Docker containers by analyzing images, layers, volumes, logs, and runtime artifacts to identify malicious activity and evidence.
- [[analyzing-malware-persistence-with-autoruns]] *(similar)* — Use Sysinternals Autoruns to systematically identify and analyze malware persistence mechanisms across registry keys, scheduled tasks, services, drivers, and startup locations on Windows systems.
- [[performing-endpoint-forensics-investigation]] *(similar)* — Performs digital forensics investigation on compromised endpoints including memory acquisition, disk imaging, artifact analysis, and timeline reconstruction. Use when investigating security incidents, collecting evidence for legal proceedings, or analyzing endpoint compromise scope. Activates for re
- [[performing-firmware-malware-analysis]] *(similar)* — Analyzes firmware images for embedded malware, backdoors, and unauthorized modifications targeting routers, IoT devices, UEFI/BIOS, and embedded systems. Covers firmware extraction, filesystem analysis, binary reverse engineering, and bootkit detection. Activates for requests involving firmware secu
- [[performing-malware-persistence-investigation]] *(similar)* — Systematically investigate all persistence mechanisms on Windows and Linux systems to identify how malware survives reboots and maintains access.
- [[detecting-process-injection-techniques]] *(complement)* — Detects and analyzes process injection techniques used by malware including classic DLL injection, process hollowing, APC injection, thread hijacking, and reflective loading. Uses memory forensics, API monitoring, and behavioral analysis to identify injection artifacts. Activates for requests involv
- [[analyzing-bootkit-and-rootkit-samples]] *(similar)* — Analyzes bootkit and advanced rootkit malware that infects the Master Boot Record (MBR), Volume Boot Record (VBR), or UEFI firmware to gain persistence below the operating system. Covers boot sector analysis, UEFI module inspection, and anti-rootkit detection techniques. Activates for requests invol
- [[detecting-fileless-malware-techniques]] *(similar)* — Detects and analyzes fileless malware that operates entirely in memory using PowerShell, WMI, .NET reflection, registry-resident payloads, and living-off-the-land binaries (LOLBins) without writing traditional executable files to disk. Activates for requests involving fileless threat detection, in-m

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
