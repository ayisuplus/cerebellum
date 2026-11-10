---
title: analyzing-slack-space-and-file-system-artifacts
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-mft-for-deleted-file-recovery, analyzing-windows-registry-for-artifacts, parsing-artifacts-with-eric-zimmerman-tools]
confidence: medium
---

Examine file system slack space, MFT entries, USN journal, and alternate data streams to recover hidden data and reconstruct file activity on NTFS volumes.

## Metadata

- **ID:** `analyzing-slack-space-and-file-system-artifacts`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/analyzing-slack-space-and-file-system-artifacts/SKILL.md`
- **Score:** 42.0
- **Edges:** 3

## Related Skills

- [[analyzing-mft-for-deleted-file-recovery]] *(bridge)* — Analyze the NTFS Master File Table ($MFT) to recover metadata and content of deleted files by examining MFT record entries, $LogFile, $UsnJrnl, and MFT slack space using MFTECmd, analyzeMFT, and X-Ways Forensics.
- [[analyzing-windows-registry-for-artifacts]] *(similar)* — Extract and analyze Windows Registry hives to uncover user activity, installed software, autostart entries, and evidence of system compromise.
- [[parsing-artifacts-with-eric-zimmerman-tools]] *(similar)* — Parse registry, prefetch, shellbags, and MFT with EZ Tools and Timeline Explorer.

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
