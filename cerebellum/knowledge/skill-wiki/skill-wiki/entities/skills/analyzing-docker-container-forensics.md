---
title: analyzing-docker-container-forensics
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-disk-image-with-autopsy, analyzing-linux-elf-malware, analyzing-malware-persistence-with-autoruns, analyzing-outlook-pst-for-email-forensics, analyzing-windows-amcache-artifacts, collecting-volatile-evidence-from-compromised-host, detecting-rootkit-activity, extracting-browser-history-artifacts, extracting-credentials-from-memory-dump, performing-cloud-forensics-investigation, performing-endpoint-forensics-investigation, performing-malware-persistence-investigation]
confidence: medium
---

Investigate compromised Docker containers by analyzing images, layers, volumes, logs, and runtime artifacts to identify malicious activity and evidence.

## Metadata

- **ID:** `analyzing-docker-container-forensics`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/analyzing-docker-container-forensics/SKILL.md`
- **Score:** 40.0
- **Edges:** 12

## Related Skills

- [[analyzing-linux-elf-malware]] *(similar)* — Analyzes malicious Linux ELF (Executable and Linkable Format) binaries including botnets, cryptominers, ransomware, and rootkits targeting Linux servers, containers, and cloud infrastructure. Covers static analysis, dynamic tracing, and reverse engineering of x86_64 and ARM ELF samples. Activates fo
- [[analyzing-malware-persistence-with-autoruns]] *(similar)* — Use Sysinternals Autoruns to systematically identify and analyze malware persistence mechanisms across registry keys, scheduled tasks, services, drivers, and startup locations on Windows systems.
- [[analyzing-windows-amcache-artifacts]] *(similar)* — Parses and analyzes the Windows Amcache.hve registry hive to extract evidence of program execution, application installation, and driver loading for digital forensics investigations. Uses Eric Zimmerman's AmcacheParser and Timeline Explorer for artifact extraction, SHA-1 hash correlation with threat
- [[performing-cloud-forensics-investigation]] *(similar)* — Conduct forensic investigations in cloud environments by collecting and analyzing logs, snapshots, and metadata from AWS, Azure, and GCP services.
- [[performing-endpoint-forensics-investigation]] *(similar)* — Performs digital forensics investigation on compromised endpoints including memory acquisition, disk imaging, artifact analysis, and timeline reconstruction. Use when investigating security incidents, collecting evidence for legal proceedings, or analyzing endpoint compromise scope. Activates for re
- [[analyzing-disk-image-with-autopsy]] *(similar)* — Perform comprehensive forensic analysis of disk images using Autopsy to recover files, examine artifacts, and build investigation timelines.
- [[analyzing-outlook-pst-for-email-forensics]] *(similar)* — Analyze Microsoft Outlook PST and OST files for email forensic evidence including message content, headers, attachments, deleted items, and metadata using libpff, pst-utils, and forensic email analysis tools for legal investigations and incident response.
- [[collecting-volatile-evidence-from-compromised-host]] *(similar)* — Collect volatile forensic evidence from a compromised system following order of volatility, preserving memory, network connections, processes, and system state before they are lost.
- [[detecting-rootkit-activity]] *(similar)* — Detects rootkit presence on compromised systems by identifying hidden processes, hooked system calls, modified kernel structures, hidden files, and covert network connections using memory forensics, cross-view detection, and integrity checking techniques. Activates for requests involving rootkit det
- [[extracting-browser-history-artifacts]] *(similar)* — Extract and analyze browser history, cookies, cache, downloads, and bookmarks from Chrome, Firefox, and Edge for forensic evidence of user web activity.
- [[extracting-credentials-from-memory-dump]] *(similar)* — Extract cached credentials, password hashes, Kerberos tickets, and authentication tokens from memory dumps using Volatility and Mimikatz for forensic investigation.
- [[performing-malware-persistence-investigation]] *(similar)* — Systematically investigate all persistence mechanisms on Windows and Linux systems to identify how malware survives reboots and maintains access.

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
