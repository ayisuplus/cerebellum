---
title: analyzing-mft-for-deleted-file-recovery
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-disk-image-with-autopsy, analyzing-outlook-pst-for-email-forensics, analyzing-slack-space-and-file-system-artifacts, analyzing-windows-lnk-files-for-artifacts, hunting-for-defense-evasion-via-timestomping, performing-file-carving-with-foremost, recovering-deleted-files-with-photorec]
confidence: low
---

Analyze the NTFS Master File Table ($MFT) to recover metadata and content of deleted files by examining MFT record entries, $LogFile, $UsnJrnl, and MFT slack space using MFTECmd, analyzeMFT, and X-Ways Forensics.

## Metadata

- **ID:** `analyzing-mft-for-deleted-file-recovery`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/analyzing-mft-for-deleted-file-recovery/SKILL.md`
- **Score:** 32.0
- **Edges:** 7

## Related Skills

- [[analyzing-outlook-pst-for-email-forensics]] *(similar)* — Analyze Microsoft Outlook PST and OST files for email forensic evidence including message content, headers, attachments, deleted items, and metadata using libpff, pst-utils, and forensic email analysis tools for legal investigations and incident response.
- [[analyzing-windows-lnk-files-for-artifacts]] *(similar)* — Parse Windows LNK shortcut files to extract target paths, timestamps, volume information, and machine identifiers for forensic timeline reconstruction.
- [[hunting-for-defense-evasion-via-timestomping]] *(similar)* — Detect NTFS timestamp manipulation (MITRE T1070.006) by comparing $STANDARD_INFORMATION vs $FILE_NAME timestamps in the MFT. Uses analyzeMFT and Python to identify files with anomalous temporal patterns indicating anti-forensic timestomping activity.

- [[performing-file-carving-with-foremost]] *(similar)* — Recover files from disk images and unallocated space using Foremost's header-footer signature carving to extract evidence regardless of file system state.
- [[recovering-deleted-files-with-photorec]] *(similar)* — Recover deleted files from disk images and storage media using PhotoRec's file signature-based carving engine regardless of file system damage.
- [[analyzing-slack-space-and-file-system-artifacts]] *(bridge)* — Examine file system slack space, MFT entries, USN journal, and alternate data streams to recover hidden data and reconstruct file activity on NTFS volumes.
- [[analyzing-disk-image-with-autopsy]] *(similar)* — Perform comprehensive forensic analysis of disk images using Autopsy to recover files, examine artifacts, and build investigation timelines.

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
