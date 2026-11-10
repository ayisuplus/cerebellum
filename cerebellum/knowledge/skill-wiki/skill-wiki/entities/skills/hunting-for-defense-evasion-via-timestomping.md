---
title: hunting-for-defense-evasion-via-timestomping
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-disk-image-with-autopsy, analyzing-malware-sandbox-evasion-techniques, analyzing-mft-for-deleted-file-recovery, analyzing-windows-amcache-artifacts, analyzing-windows-lnk-files-for-artifacts, generating-forensic-timelines-with-hayabusa, hunting-for-shadow-copy-deletion]
confidence: medium
---

Detect NTFS timestamp manipulation (MITRE T1070.006) by comparing $STANDARD_INFORMATION vs $FILE_NAME timestamps in the MFT. Uses analyzeMFT and Python to identify files with anomalous temporal patterns indicating anti-forensic timestomping activity.

## Metadata

- **ID:** `hunting-for-defense-evasion-via-timestomping`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/hunting-for-defense-evasion-via-timestomping/SKILL.md`
- **Score:** 48.0
- **Edges:** 7

## Related Skills

- [[analyzing-disk-image-with-autopsy]] *(similar)* — Perform comprehensive forensic analysis of disk images using Autopsy to recover files, examine artifacts, and build investigation timelines.
- [[analyzing-malware-sandbox-evasion-techniques]] *(similar)* — Detect sandbox evasion techniques in malware samples by analyzing timing checks, VM artifact queries, user interaction detection, and sleep inflation patterns from Cuckoo/AnyRun behavioral reports
- [[analyzing-windows-amcache-artifacts]] *(similar)* — Parses and analyzes the Windows Amcache.hve registry hive to extract evidence of program execution, application installation, and driver loading for digital forensics investigations. Uses Eric Zimmerman's AmcacheParser and Timeline Explorer for artifact extraction, SHA-1 hash correlation with threat
- [[generating-forensic-timelines-with-hayabusa]] *(similar)* — Produce Sigma-based EVTX timelines and summaries with Hayabusa.
- [[hunting-for-shadow-copy-deletion]] *(similar)* — Hunt for Volume Shadow Copy deletion activity that indicates ransomware preparation or anti-forensics by monitoring vssadmin, wmic, and PowerShell shadow copy commands.
- [[analyzing-mft-for-deleted-file-recovery]] *(similar)* — Analyze the NTFS Master File Table ($MFT) to recover metadata and content of deleted files by examining MFT record entries, $LogFile, $UsnJrnl, and MFT slack space using MFTECmd, analyzeMFT, and X-Ways Forensics.
- [[analyzing-windows-lnk-files-for-artifacts]] *(similar)* — Parse Windows LNK shortcut files to extract target paths, timestamps, volume information, and machine identifiers for forensic timeline reconstruction.

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
