---
title: hunting-for-shadow-copy-deletion
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [detecting-fileless-malware-techniques, hunting-advanced-persistent-threats, hunting-for-defense-evasion-via-timestomping]
confidence: low
---

Hunt for Volume Shadow Copy deletion activity that indicates ransomware preparation or anti-forensics by monitoring vssadmin, wmic, and PowerShell shadow copy commands.

## Metadata

- **ID:** `hunting-for-shadow-copy-deletion`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/hunting-for-shadow-copy-deletion/SKILL.md`
- **Score:** 31.0
- **Edges:** 3

## Related Skills

- [[detecting-fileless-malware-techniques]] *(similar)* — Detects and analyzes fileless malware that operates entirely in memory using PowerShell, WMI, .NET reflection, registry-resident payloads, and living-off-the-land binaries (LOLBins) without writing traditional executable files to disk. Activates for requests involving fileless threat detection, in-m
- [[hunting-advanced-persistent-threats]] *(similar)* — Proactively hunts for Advanced Persistent Threat (APT) activity within enterprise environments using hypothesis-driven searches across endpoint telemetry, network logs, and memory artifacts. Use when conducting scheduled threat hunting cycles, investigating anomalous behavior flagged by UEBA, or val
- [[hunting-for-defense-evasion-via-timestomping]] *(similar)* — Detect NTFS timestamp manipulation (MITRE T1070.006) by comparing $STANDARD_INFORMATION vs $FILE_NAME timestamps in the MFT. Uses analyzeMFT and Python to identify files with anomalous temporal patterns indicating anti-forensic timestomping activity.


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
