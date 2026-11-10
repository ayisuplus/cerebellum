---
title: extracting-credentials-from-memory-dump
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-disk-image-with-autopsy, analyzing-docker-container-forensics, analyzing-outlook-pst-for-email-forensics, analyzing-windows-amcache-artifacts, analyzing-windows-lnk-files-for-artifacts, collecting-volatile-evidence-from-compromised-host, extracting-browser-history-artifacts, performing-endpoint-forensics-investigation, performing-file-carving-with-foremost, triaging-windows-with-kape]
confidence: medium
---

Extract cached credentials, password hashes, Kerberos tickets, and authentication tokens from memory dumps using Volatility and Mimikatz for forensic investigation.

## Metadata

- **ID:** `extracting-credentials-from-memory-dump`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/extracting-credentials-from-memory-dump/SKILL.md`
- **Score:** 46.0
- **Edges:** 10

## Related Skills

- [[analyzing-disk-image-with-autopsy]] *(similar)* — Perform comprehensive forensic analysis of disk images using Autopsy to recover files, examine artifacts, and build investigation timelines.
- [[analyzing-docker-container-forensics]] *(similar)* — Investigate compromised Docker containers by analyzing images, layers, volumes, logs, and runtime artifacts to identify malicious activity and evidence.
- [[performing-endpoint-forensics-investigation]] *(similar)* — Performs digital forensics investigation on compromised endpoints including memory acquisition, disk imaging, artifact analysis, and timeline reconstruction. Use when investigating security incidents, collecting evidence for legal proceedings, or analyzing endpoint compromise scope. Activates for re
- [[performing-file-carving-with-foremost]] *(similar)* — Recover files from disk images and unallocated space using Foremost's header-footer signature carving to extract evidence regardless of file system state.
- [[triaging-windows-with-kape]] *(similar)* — Run targeted forensic artifact collection and module parsing with KAPE.
- [[analyzing-outlook-pst-for-email-forensics]] *(similar)* — Analyze Microsoft Outlook PST and OST files for email forensic evidence including message content, headers, attachments, deleted items, and metadata using libpff, pst-utils, and forensic email analysis tools for legal investigations and incident response.
- [[analyzing-windows-amcache-artifacts]] *(similar)* — Parses and analyzes the Windows Amcache.hve registry hive to extract evidence of program execution, application installation, and driver loading for digital forensics investigations. Uses Eric Zimmerman's AmcacheParser and Timeline Explorer for artifact extraction, SHA-1 hash correlation with threat
- [[analyzing-windows-lnk-files-for-artifacts]] *(similar)* — Parse Windows LNK shortcut files to extract target paths, timestamps, volume information, and machine identifiers for forensic timeline reconstruction.
- [[collecting-volatile-evidence-from-compromised-host]] *(similar)* — Collect volatile forensic evidence from a compromised system following order of volatility, preserving memory, network connections, processes, and system state before they are lost.
- [[extracting-browser-history-artifacts]] *(similar)* — Extract and analyze browser history, cookies, cache, downloads, and bookmarks from Chrome, Firefox, and Edge for forensic evidence of user web activity.

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
