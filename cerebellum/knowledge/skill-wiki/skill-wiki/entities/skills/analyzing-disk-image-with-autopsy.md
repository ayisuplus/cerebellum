---
title: analyzing-disk-image-with-autopsy
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [acquiring-disk-image-with-dd-and-dcfldd, analyzing-docker-container-forensics, analyzing-malware-persistence-with-autoruns, analyzing-mft-for-deleted-file-recovery, analyzing-outlook-pst-for-email-forensics, analyzing-windows-amcache-artifacts, analyzing-windows-lnk-files-for-artifacts, building-incident-timeline-with-timesketch, collecting-volatile-evidence-from-compromised-host, extracting-browser-history-artifacts, extracting-credentials-from-memory-dump, generating-forensic-timelines-with-hayabusa, hunting-for-defense-evasion-via-timestomping, implementing-velociraptor-for-ir-collection, performing-cloud-forensics-investigation, performing-cloud-storage-forensic-acquisition, performing-endpoint-forensics-investigation, performing-file-carving-with-foremost, performing-mobile-device-forensics-with-cellebrite, recovering-deleted-files-with-photorec, triaging-windows-with-kape]
confidence: medium
---

Perform comprehensive forensic analysis of disk images using Autopsy to recover files, examine artifacts, and build investigation timelines.

## Metadata

- **ID:** `analyzing-disk-image-with-autopsy`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/analyzing-disk-image-with-autopsy/SKILL.md`
- **Score:** 41.0
- **Edges:** 21

## Related Skills

- [[performing-endpoint-forensics-investigation]] *(complement)* — Performs digital forensics investigation on compromised endpoints including memory acquisition, disk imaging, artifact analysis, and timeline reconstruction. Use when investigating security incidents, collecting evidence for legal proceedings, or analyzing endpoint compromise scope. Activates for re
- [[performing-file-carving-with-foremost]] *(complement)* — Recover files from disk images and unallocated space using Foremost's header-footer signature carving to extract evidence regardless of file system state.
- [[analyzing-docker-container-forensics]] *(similar)* — Investigate compromised Docker containers by analyzing images, layers, volumes, logs, and runtime artifacts to identify malicious activity and evidence.
- [[analyzing-mft-for-deleted-file-recovery]] *(similar)* — Analyze the NTFS Master File Table ($MFT) to recover metadata and content of deleted files by examining MFT record entries, $LogFile, $UsnJrnl, and MFT slack space using MFTECmd, analyzeMFT, and X-Ways Forensics.
- [[analyzing-outlook-pst-for-email-forensics]] *(similar)* — Analyze Microsoft Outlook PST and OST files for email forensic evidence including message content, headers, attachments, deleted items, and metadata using libpff, pst-utils, and forensic email analysis tools for legal investigations and incident response.
- [[acquiring-disk-image-with-dd-and-dcfldd]] *(similar)* — Create forensically sound bit-for-bit disk images using dd and dcfldd while preserving evidence integrity through hash verification.
- [[analyzing-malware-persistence-with-autoruns]] *(similar)* — Use Sysinternals Autoruns to systematically identify and analyze malware persistence mechanisms across registry keys, scheduled tasks, services, drivers, and startup locations on Windows systems.
- [[analyzing-windows-amcache-artifacts]] *(similar)* — Parses and analyzes the Windows Amcache.hve registry hive to extract evidence of program execution, application installation, and driver loading for digital forensics investigations. Uses Eric Zimmerman's AmcacheParser and Timeline Explorer for artifact extraction, SHA-1 hash correlation with threat
- [[analyzing-windows-lnk-files-for-artifacts]] *(similar)* — Parse Windows LNK shortcut files to extract target paths, timestamps, volume information, and machine identifiers for forensic timeline reconstruction.
- [[building-incident-timeline-with-timesketch]] *(similar)* — Build collaborative forensic incident timelines using Timesketch to ingest, normalize, and analyze multi-source event data for attack chain reconstruction and investigation documentation.
- [[collecting-volatile-evidence-from-compromised-host]] *(similar)* — Collect volatile forensic evidence from a compromised system following order of volatility, preserving memory, network connections, processes, and system state before they are lost.
- [[extracting-browser-history-artifacts]] *(similar)* — Extract and analyze browser history, cookies, cache, downloads, and bookmarks from Chrome, Firefox, and Edge for forensic evidence of user web activity.
- [[extracting-credentials-from-memory-dump]] *(similar)* — Extract cached credentials, password hashes, Kerberos tickets, and authentication tokens from memory dumps using Volatility and Mimikatz for forensic investigation.
- [[generating-forensic-timelines-with-hayabusa]] *(similar)* — Produce Sigma-based EVTX timelines and summaries with Hayabusa.
- [[hunting-for-defense-evasion-via-timestomping]] *(similar)* — Detect NTFS timestamp manipulation (MITRE T1070.006) by comparing $STANDARD_INFORMATION vs $FILE_NAME timestamps in the MFT. Uses analyzeMFT and Python to identify files with anomalous temporal patterns indicating anti-forensic timestomping activity.

- [[implementing-velociraptor-for-ir-collection]] *(similar)* — Deploy and configure Velociraptor for scalable endpoint forensic artifact collection during incident response using VQL queries, hunts, and pre-built artifact packs across Windows, Linux, and macOS environments.
- [[performing-cloud-forensics-investigation]] *(similar)* — Conduct forensic investigations in cloud environments by collecting and analyzing logs, snapshots, and metadata from AWS, Azure, and GCP services.
- [[performing-cloud-storage-forensic-acquisition]] *(similar)* — Perform forensic acquisition and analysis of cloud storage services including Google Drive, OneDrive, Dropbox, and Box by collecting both API-based remote data and local sync client artifacts from endpoint devices.
- [[performing-mobile-device-forensics-with-cellebrite]] *(similar)* — Acquire and analyze mobile device data using Cellebrite UFED and open-source tools to extract communications, location data, and application artifacts.
- [[recovering-deleted-files-with-photorec]] *(similar)* — Recover deleted files from disk images and storage media using PhotoRec's file signature-based carving engine regardless of file system damage.
- [[triaging-windows-with-kape]] *(similar)* — Run targeted forensic artifact collection and module parsing with KAPE.

## See Also

- [[abusing-dpapi-for-credential-access]] — Anthropic-Cybersecurity-Skills
- [[abusing-shadow-credentials-for-privesc]] — Anthropic-Cybersecurity-Skills
- [[achieving-cmmc-level-2-compliance]] — Anthropic-Cybersecurity-Skills
- [[analyzing-active-directory-acl-abuse]] — Anthropic-Cybersecurity-Skills
- [[analyzing-android-malware-with-apktool]] — Anthropic-Cybersecurity-Skills
- [[analyzing-api-gateway-access-logs]] — Anthropic-Cybersecurity-Skills
- [[analyzing-apt-group-with-mitre-navigator]] — Anthropic-Cybersecurity-Skills
- [[analyzing-azure-activity-logs-for-threats]] — Anthropic-Cybersecurity-Skills
- [[analyzing-bootkit-and-rootkit-samples]] — Anthropic-Cybersecurity-Skills
- [[analyzing-campaign-attribution-evidence]] — Anthropic-Cybersecurity-Skills
