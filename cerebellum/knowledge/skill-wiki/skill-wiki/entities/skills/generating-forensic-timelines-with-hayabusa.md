---
title: generating-forensic-timelines-with-hayabusa
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-disk-image-with-autopsy, analyzing-windows-amcache-artifacts, analyzing-windows-lnk-files-for-artifacts, building-incident-timeline-with-timesketch, extracting-browser-history-artifacts, hunting-for-defense-evasion-via-timestomping, triaging-windows-with-kape]
confidence: low
---

Produce Sigma-based EVTX timelines and summaries with Hayabusa.

## Metadata

- **ID:** `generating-forensic-timelines-with-hayabusa`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/generating-forensic-timelines-with-hayabusa/SKILL.md`
- **Score:** 36.0
- **Edges:** 7

## Related Skills

- [[analyzing-disk-image-with-autopsy]] *(similar)* — Perform comprehensive forensic analysis of disk images using Autopsy to recover files, examine artifacts, and build investigation timelines.
- [[analyzing-windows-amcache-artifacts]] *(similar)* — Parses and analyzes the Windows Amcache.hve registry hive to extract evidence of program execution, application installation, and driver loading for digital forensics investigations. Uses Eric Zimmerman's AmcacheParser and Timeline Explorer for artifact extraction, SHA-1 hash correlation with threat
- [[analyzing-windows-lnk-files-for-artifacts]] *(similar)* — Parse Windows LNK shortcut files to extract target paths, timestamps, volume information, and machine identifiers for forensic timeline reconstruction.
- [[extracting-browser-history-artifacts]] *(similar)* — Extract and analyze browser history, cookies, cache, downloads, and bookmarks from Chrome, Firefox, and Edge for forensic evidence of user web activity.
- [[triaging-windows-with-kape]] *(similar)* — Run targeted forensic artifact collection and module parsing with KAPE.
- [[building-incident-timeline-with-timesketch]] *(similar)* — Build collaborative forensic incident timelines using Timesketch to ingest, normalize, and analyze multi-source event data for attack chain reconstruction and investigation documentation.
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
