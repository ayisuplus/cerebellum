---
title: analyzing-windows-lnk-files-for-artifacts
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-disk-image-with-autopsy, analyzing-mft-for-deleted-file-recovery, analyzing-outlook-pst-for-email-forensics, analyzing-windows-amcache-artifacts, analyzing-windows-registry-for-artifacts, extracting-browser-history-artifacts, extracting-credentials-from-memory-dump, generating-forensic-timelines-with-hayabusa, hunting-for-defense-evasion-via-timestomping, triaging-windows-with-kape]
confidence: low
---

Parse Windows LNK shortcut files to extract target paths, timestamps, volume information, and machine identifiers for forensic timeline reconstruction.

## Metadata

- **ID:** `analyzing-windows-lnk-files-for-artifacts`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/analyzing-windows-lnk-files-for-artifacts/SKILL.md`
- **Score:** 36.0
- **Edges:** 10

## Related Skills

- [[analyzing-disk-image-with-autopsy]] *(similar)* — Perform comprehensive forensic analysis of disk images using Autopsy to recover files, examine artifacts, and build investigation timelines.
- [[extracting-browser-history-artifacts]] *(similar)* — Extract and analyze browser history, cookies, cache, downloads, and bookmarks from Chrome, Firefox, and Edge for forensic evidence of user web activity.
- [[extracting-credentials-from-memory-dump]] *(similar)* — Extract cached credentials, password hashes, Kerberos tickets, and authentication tokens from memory dumps using Volatility and Mimikatz for forensic investigation.
- [[hunting-for-defense-evasion-via-timestomping]] *(similar)* — Detect NTFS timestamp manipulation (MITRE T1070.006) by comparing $STANDARD_INFORMATION vs $FILE_NAME timestamps in the MFT. Uses analyzeMFT and Python to identify files with anomalous temporal patterns indicating anti-forensic timestomping activity.

- [[triaging-windows-with-kape]] *(similar)* — Run targeted forensic artifact collection and module parsing with KAPE.
- [[analyzing-windows-registry-for-artifacts]] *(bridge)* — Extract and analyze Windows Registry hives to uncover user activity, installed software, autostart entries, and evidence of system compromise.
- [[analyzing-windows-amcache-artifacts]] *(complement)* — Parses and analyzes the Windows Amcache.hve registry hive to extract evidence of program execution, application installation, and driver loading for digital forensics investigations. Uses Eric Zimmerman's AmcacheParser and Timeline Explorer for artifact extraction, SHA-1 hash correlation with threat
- [[analyzing-mft-for-deleted-file-recovery]] *(similar)* — Analyze the NTFS Master File Table ($MFT) to recover metadata and content of deleted files by examining MFT record entries, $LogFile, $UsnJrnl, and MFT slack space using MFTECmd, analyzeMFT, and X-Ways Forensics.
- [[analyzing-outlook-pst-for-email-forensics]] *(similar)* — Analyze Microsoft Outlook PST and OST files for email forensic evidence including message content, headers, attachments, deleted items, and metadata using libpff, pst-utils, and forensic email analysis tools for legal investigations and incident response.
- [[generating-forensic-timelines-with-hayabusa]] *(similar)* — Produce Sigma-based EVTX timelines and summaries with Hayabusa.

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
