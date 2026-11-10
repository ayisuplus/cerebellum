---
title: hunting-for-registry-run-key-persistence
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [detecting-credential-dumping-techniques, detecting-living-off-the-land-attacks, detecting-malicious-scheduled-tasks-with-sysmon, detecting-wmi-persistence, hunting-bootkits-in-efi-system-partition, hunting-for-ntlm-relay-attacks, hunting-for-startup-folder-persistence, hunting-for-unusual-service-installations]
confidence: low
---

Detect MITRE ATT&CK T1547.001 registry Run key persistence by analyzing Sysmon Event ID 13 logs and registry queries to identify malicious auto-start entries.

## Metadata

- **ID:** `hunting-for-registry-run-key-persistence`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/hunting-for-registry-run-key-persistence/SKILL.md`
- **Score:** 33.0
- **Edges:** 8

## Related Skills

- [[hunting-for-startup-folder-persistence]] *(complement)* — Detect T1547.001 startup folder persistence by monitoring Windows startup directories for suspicious file creation, analyzing autoruns entries, and using Python watchdog for real-time filesystem monitoring.
- [[hunting-for-unusual-service-installations]] *(complement)* — Detect suspicious Windows service installations (MITRE ATT&CK T1543.003) by parsing System event logs for Event ID 7045, analyzing service binary paths, and identifying indicators of persistence mechanisms.
- [[detecting-credential-dumping-techniques]] *(similar)* — Detect LSASS credential dumping, SAM database extraction, and NTDS.dit theft using Sysmon Event ID 10, Windows Security logs, and SIEM correlation rules
- [[detecting-living-off-the-land-attacks]] *(similar)* — Detect abuse of legitimate Windows binaries (LOLBins) used for living off the land attacks. Monitors process creation, command-line arguments, and parent-child relationships to identify suspicious LOLBin execution patterns.

- [[hunting-for-ntlm-relay-attacks]] *(similar)* — Detect NTLM relay attacks by analyzing Windows Event 4624 logon type 3 with NTLMSSP authentication, identifying IP-to-hostname mismatches, Responder traffic signatures, SMB signing status, and suspicious authentication patterns across the domain.
- [[detecting-wmi-persistence]] *(complement)* — Detect WMI event subscription persistence by analyzing Sysmon Event IDs 19, 20, and 21 for malicious EventFilter, EventConsumer, and FilterToConsumerBinding creation.
- [[detecting-malicious-scheduled-tasks-with-sysmon]] *(similar)* — Detect malicious scheduled task creation and modification using Sysmon Event IDs 1 (Process Create for schtasks.exe), 11 (File Create for task XML), and Windows Security Event 4698/4702. The analyst correlates task creation with suspicious parent processes, public directory paths, and encoded comman
- [[hunting-bootkits-in-efi-system-partition]] *(similar)* — Baseline the EFI System Partition and hunt malicious EFI binaries (ESPecter, BlackLotus, Bootkitty, Glupteba) by mounting the ESP, hashing and verifying boot loaders, scanning with YARA, and detecting anomalous non-EFI files.

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
