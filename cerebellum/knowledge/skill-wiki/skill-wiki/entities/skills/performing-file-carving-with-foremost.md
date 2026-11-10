---
title: performing-file-carving-with-foremost
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [acquiring-disk-image-with-dd-and-dcfldd, analyzing-disk-image-with-autopsy, analyzing-mft-for-deleted-file-recovery, analyzing-outlook-pst-for-email-forensics, collecting-volatile-evidence-from-compromised-host, extracting-credentials-from-memory-dump, performing-cloud-forensics-investigation, performing-endpoint-forensics-investigation, performing-firmware-malware-analysis, performing-mobile-device-forensics-with-cellebrite, recovering-deleted-files-with-photorec]
confidence: low
---

Recover files from disk images and unallocated space using Foremost's header-footer signature carving to extract evidence regardless of file system state.

## Metadata

- **ID:** `performing-file-carving-with-foremost`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/performing-file-carving-with-foremost/SKILL.md`
- **Score:** 37.0
- **Edges:** 11

## Related Skills

- [[recovering-deleted-files-with-photorec]] *(complement)* — Recover deleted files from disk images and storage media using PhotoRec's file signature-based carving engine regardless of file system damage.
- [[performing-cloud-forensics-investigation]] *(similar)* — Conduct forensic investigations in cloud environments by collecting and analyzing logs, snapshots, and metadata from AWS, Azure, and GCP services.
- [[performing-endpoint-forensics-investigation]] *(similar)* — Performs digital forensics investigation on compromised endpoints including memory acquisition, disk imaging, artifact analysis, and timeline reconstruction. Use when investigating security incidents, collecting evidence for legal proceedings, or analyzing endpoint compromise scope. Activates for re
- [[performing-firmware-malware-analysis]] *(similar)* — Analyzes firmware images for embedded malware, backdoors, and unauthorized modifications targeting routers, IoT devices, UEFI/BIOS, and embedded systems. Covers firmware extraction, filesystem analysis, binary reverse engineering, and bootkit detection. Activates for requests involving firmware secu
- [[performing-mobile-device-forensics-with-cellebrite]] *(similar)* — Acquire and analyze mobile device data using Cellebrite UFED and open-source tools to extract communications, location data, and application artifacts.
- [[analyzing-disk-image-with-autopsy]] *(complement)* — Perform comprehensive forensic analysis of disk images using Autopsy to recover files, examine artifacts, and build investigation timelines.
- [[acquiring-disk-image-with-dd-and-dcfldd]] *(similar)* — Create forensically sound bit-for-bit disk images using dd and dcfldd while preserving evidence integrity through hash verification.
- [[analyzing-mft-for-deleted-file-recovery]] *(similar)* — Analyze the NTFS Master File Table ($MFT) to recover metadata and content of deleted files by examining MFT record entries, $LogFile, $UsnJrnl, and MFT slack space using MFTECmd, analyzeMFT, and X-Ways Forensics.
- [[analyzing-outlook-pst-for-email-forensics]] *(similar)* — Analyze Microsoft Outlook PST and OST files for email forensic evidence including message content, headers, attachments, deleted items, and metadata using libpff, pst-utils, and forensic email analysis tools for legal investigations and incident response.
- [[collecting-volatile-evidence-from-compromised-host]] *(similar)* — Collect volatile forensic evidence from a compromised system following order of volatility, preserving memory, network connections, processes, and system state before they are lost.
- [[extracting-credentials-from-memory-dump]] *(similar)* — Extract cached credentials, password hashes, Kerberos tickets, and authentication tokens from memory dumps using Volatility and Mimikatz for forensic investigation.

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
