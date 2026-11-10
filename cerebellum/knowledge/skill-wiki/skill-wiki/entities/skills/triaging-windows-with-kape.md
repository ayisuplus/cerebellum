---
title: triaging-windows-with-kape
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-disk-image-with-autopsy, analyzing-malware-persistence-with-autoruns, analyzing-windows-amcache-artifacts, analyzing-windows-lnk-files-for-artifacts, building-incident-timeline-with-timesketch, extracting-browser-history-artifacts, extracting-credentials-from-memory-dump, generating-forensic-timelines-with-hayabusa, implementing-velociraptor-for-ir-collection, performing-automated-malware-analysis-with-cape, performing-cloud-storage-forensic-acquisition, performing-endpoint-forensics-investigation, performing-malware-hash-enrichment-with-virustotal, performing-malware-persistence-investigation]
confidence: low
---

Run targeted forensic artifact collection and module parsing with KAPE.

## Metadata

- **ID:** `triaging-windows-with-kape`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/triaging-windows-with-kape/SKILL.md`
- **Score:** 38.0
- **Edges:** 14

## Related Skills

- [[analyzing-disk-image-with-autopsy]] *(similar)* — Perform comprehensive forensic analysis of disk images using Autopsy to recover files, examine artifacts, and build investigation timelines.
- [[analyzing-malware-persistence-with-autoruns]] *(similar)* — Use Sysinternals Autoruns to systematically identify and analyze malware persistence mechanisms across registry keys, scheduled tasks, services, drivers, and startup locations on Windows systems.
- [[extracting-browser-history-artifacts]] *(similar)* — Extract and analyze browser history, cookies, cache, downloads, and bookmarks from Chrome, Firefox, and Edge for forensic evidence of user web activity.
- [[performing-malware-hash-enrichment-with-virustotal]] *(similar)* — Enrich malware file hashes using the VirusTotal API to retrieve detection rates, behavioral analysis, YARA matches, and contextual threat intelligence for incident triage and IOC validation.
- [[performing-malware-persistence-investigation]] *(similar)* — Systematically investigate all persistence mechanisms on Windows and Linux systems to identify how malware survives reboots and maintains access.
- [[analyzing-windows-amcache-artifacts]] *(similar)* — Parses and analyzes the Windows Amcache.hve registry hive to extract evidence of program execution, application installation, and driver loading for digital forensics investigations. Uses Eric Zimmerman's AmcacheParser and Timeline Explorer for artifact extraction, SHA-1 hash correlation with threat
- [[analyzing-windows-lnk-files-for-artifacts]] *(similar)* — Parse Windows LNK shortcut files to extract target paths, timestamps, volume information, and machine identifiers for forensic timeline reconstruction.
- [[building-incident-timeline-with-timesketch]] *(similar)* — Build collaborative forensic incident timelines using Timesketch to ingest, normalize, and analyze multi-source event data for attack chain reconstruction and investigation documentation.
- [[extracting-credentials-from-memory-dump]] *(similar)* — Extract cached credentials, password hashes, Kerberos tickets, and authentication tokens from memory dumps using Volatility and Mimikatz for forensic investigation.
- [[generating-forensic-timelines-with-hayabusa]] *(similar)* — Produce Sigma-based EVTX timelines and summaries with Hayabusa.
- [[implementing-velociraptor-for-ir-collection]] *(similar)* — Deploy and configure Velociraptor for scalable endpoint forensic artifact collection during incident response using VQL queries, hunts, and pre-built artifact packs across Windows, Linux, and macOS environments.
- [[performing-automated-malware-analysis-with-cape]] *(similar)* — Deploy and operate CAPEv2 sandbox for automated malware analysis with behavioral monitoring, payload extraction, configuration parsing, and anti-evasion capabilities.
- [[performing-cloud-storage-forensic-acquisition]] *(similar)* — Perform forensic acquisition and analysis of cloud storage services including Google Drive, OneDrive, Dropbox, and Box by collecting both API-based remote data and local sync client artifacts from endpoint devices.
- [[performing-endpoint-forensics-investigation]] *(similar)* — Performs digital forensics investigation on compromised endpoints including memory acquisition, disk imaging, artifact analysis, and timeline reconstruction. Use when investigating security incidents, collecting evidence for legal proceedings, or analyzing endpoint compromise scope. Activates for re

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
