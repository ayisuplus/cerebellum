---
title: performing-endpoint-forensics-investigation
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [acquiring-disk-image-with-dd-and-dcfldd, analyzing-disk-image-with-autopsy, analyzing-docker-container-forensics, analyzing-windows-amcache-artifacts, building-incident-timeline-with-timesketch, collecting-volatile-evidence-from-compromised-host, conducting-cloud-incident-response, conducting-malware-incident-response, detecting-rootkit-activity, extracting-credentials-from-memory-dump, hunting-advanced-persistent-threats, implementing-velociraptor-for-ir-collection, investigating-phishing-email-incident, performing-cloud-forensics-investigation, performing-cloud-incident-containment-procedures, performing-cloud-storage-forensic-acquisition, performing-file-carving-with-foremost, performing-insider-threat-investigation, performing-malware-persistence-investigation, performing-mobile-device-forensics-with-cellebrite, performing-ransomware-response, triaging-security-incident, triaging-windows-with-kape]
confidence: medium
---

Performs digital forensics investigation on compromised endpoints including memory acquisition, disk imaging, artifact analysis, and timeline reconstruction. Use when investigating security incidents, collecting evidence for legal proceedings, or analyzing endpoint compromise scope. Activates for re

## Metadata

- **ID:** `performing-endpoint-forensics-investigation`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/performing-endpoint-forensics-investigation/SKILL.md`
- **Score:** 58.0
- **Edges:** 23

## Related Skills

- [[analyzing-windows-amcache-artifacts]] *(similar)* — Parses and analyzes the Windows Amcache.hve registry hive to extract evidence of program execution, application installation, and driver loading for digital forensics investigations. Uses Eric Zimmerman's AmcacheParser and Timeline Explorer for artifact extraction, SHA-1 hash correlation with threat
- [[conducting-cloud-incident-response]] *(similar)* — Responds to security incidents in cloud environments (AWS, Azure, GCP) by performing identity-based containment, cloud-native log analysis, resource isolation, and forensic evidence acquisition adapted for ephemeral cloud infrastructure. Activates for requests involving cloud incident response, AWS 
- [[performing-insider-threat-investigation]] *(similar)* — Investigates insider threat incidents involving employees, contractors, or trusted partners who misuse authorized access to steal data, sabotage systems, or violate security policies. Combines digital forensics, user behavior analytics, and HR/legal coordination to build an evidence-based case. Acti
- [[performing-malware-persistence-investigation]] *(similar)* — Systematically investigate all persistence mechanisms on Windows and Linux systems to identify how malware survives reboots and maintains access.
- [[triaging-windows-with-kape]] *(similar)* — Run targeted forensic artifact collection and module parsing with KAPE.
- [[analyzing-disk-image-with-autopsy]] *(complement)* — Perform comprehensive forensic analysis of disk images using Autopsy to recover files, examine artifacts, and build investigation timelines.
- [[acquiring-disk-image-with-dd-and-dcfldd]] *(similar)* — Create forensically sound bit-for-bit disk images using dd and dcfldd while preserving evidence integrity through hash verification.
- [[analyzing-docker-container-forensics]] *(similar)* — Investigate compromised Docker containers by analyzing images, layers, volumes, logs, and runtime artifacts to identify malicious activity and evidence.
- [[building-incident-timeline-with-timesketch]] *(similar)* — Build collaborative forensic incident timelines using Timesketch to ingest, normalize, and analyze multi-source event data for attack chain reconstruction and investigation documentation.
- [[collecting-volatile-evidence-from-compromised-host]] *(similar)* — Collect volatile forensic evidence from a compromised system following order of volatility, preserving memory, network connections, processes, and system state before they are lost.
- [[conducting-malware-incident-response]] *(similar)* — Responds to malware infections across enterprise endpoints by identifying the malware family, determining infection vectors, assessing spread, and executing eradication procedures. Covers the full lifecycle from detection through containment, analysis, removal, and recovery. Activates for requests i
- [[detecting-rootkit-activity]] *(similar)* — Detects rootkit presence on compromised systems by identifying hidden processes, hooked system calls, modified kernel structures, hidden files, and covert network connections using memory forensics, cross-view detection, and integrity checking techniques. Activates for requests involving rootkit det
- [[extracting-credentials-from-memory-dump]] *(similar)* — Extract cached credentials, password hashes, Kerberos tickets, and authentication tokens from memory dumps using Volatility and Mimikatz for forensic investigation.
- [[hunting-advanced-persistent-threats]] *(similar)* — Proactively hunts for Advanced Persistent Threat (APT) activity within enterprise environments using hypothesis-driven searches across endpoint telemetry, network logs, and memory artifacts. Use when conducting scheduled threat hunting cycles, investigating anomalous behavior flagged by UEBA, or val
- [[implementing-velociraptor-for-ir-collection]] *(similar)* — Deploy and configure Velociraptor for scalable endpoint forensic artifact collection during incident response using VQL queries, hunts, and pre-built artifact packs across Windows, Linux, and macOS environments.
- [[investigating-phishing-email-incident]] *(similar)* — Investigates phishing email incidents from initial user report through header analysis, URL/attachment detonation, impacted user identification, and containment actions using SOC tools like Splunk, Microsoft Defender, and sandbox analysis platforms. Use when a reported phishing email requires full i
- [[performing-cloud-forensics-investigation]] *(similar)* — Conduct forensic investigations in cloud environments by collecting and analyzing logs, snapshots, and metadata from AWS, Azure, and GCP services.
- [[performing-cloud-incident-containment-procedures]] *(similar)* — Execute cloud-native incident containment across AWS, Azure, and GCP by isolating compromised resources, revoking credentials, preserving forensic evidence, and applying security group restrictions to prevent lateral movement.
- [[performing-cloud-storage-forensic-acquisition]] *(similar)* — Perform forensic acquisition and analysis of cloud storage services including Google Drive, OneDrive, Dropbox, and Box by collecting both API-based remote data and local sync client artifacts from endpoint devices.
- [[performing-file-carving-with-foremost]] *(similar)* — Recover files from disk images and unallocated space using Foremost's header-footer signature carving to extract evidence regardless of file system state.
- [[performing-mobile-device-forensics-with-cellebrite]] *(similar)* — Acquire and analyze mobile device data using Cellebrite UFED and open-source tools to extract communications, location data, and application artifacts.
- [[performing-ransomware-response]] *(similar)* — Executes a structured ransomware incident response from initial detection through containment, forensic analysis, decryption assessment, recovery, and post-incident hardening. Addresses ransom negotiation considerations, backup integrity verification, and regulatory notification requirements. Activa
- [[triaging-security-incident]] *(similar)* — Performs initial triage of security incidents to determine severity, scope, and required response actions using the NIST SP 800-61r3 and SANS PICERL frameworks. Classifies incidents by type, assigns priority based on business impact, and routes to appropriate response teams. Activates for requests i

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
