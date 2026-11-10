---
title: hunting-for-startup-folder-persistence
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-persistence-mechanisms-in-linux, analyzing-usb-device-connection-history, analyzing-windows-prefetch-with-python, deploying-ransomware-canary-files, detecting-living-off-the-land-attacks, detecting-malicious-scheduled-tasks-with-sysmon, detecting-wmi-persistence, hunting-bootkits-in-efi-system-partition, hunting-for-data-staging-before-exfiltration, hunting-for-registry-run-key-persistence, hunting-for-unusual-service-installations]
confidence: low
---

Detect T1547.001 startup folder persistence by monitoring Windows startup directories for suspicious file creation, analyzing autoruns entries, and using Python watchdog for real-time filesystem monitoring.

## Metadata

- **ID:** `hunting-for-startup-folder-persistence`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/hunting-for-startup-folder-persistence/SKILL.md`
- **Score:** 27.0
- **Edges:** 11

## Related Skills

- [[analyzing-usb-device-connection-history]] *(similar)* — Investigate USB device connection history from Windows registry, event logs, and setupapi logs to track removable media usage and potential data exfiltration.
- [[analyzing-windows-prefetch-with-python]] *(similar)* — Parse Windows Prefetch files using the windowsprefetch Python library to reconstruct application execution history, detect renamed or masquerading binaries, and identify suspicious program execution patterns.
- [[detecting-living-off-the-land-attacks]] *(similar)* — Detect abuse of legitimate Windows binaries (LOLBins) used for living off the land attacks. Monitors process creation, command-line arguments, and parent-child relationships to identify suspicious LOLBin execution patterns.

- [[detecting-wmi-persistence]] *(similar)* — Detect WMI event subscription persistence by analyzing Sysmon Event IDs 19, 20, and 21 for malicious EventFilter, EventConsumer, and FilterToConsumerBinding creation.
- [[hunting-for-unusual-service-installations]] *(similar)* — Detect suspicious Windows service installations (MITRE ATT&CK T1543.003) by parsing System event logs for Event ID 7045, analyzing service binary paths, and identifying indicators of persistence mechanisms.
- [[hunting-for-registry-run-key-persistence]] *(complement)* — Detect MITRE ATT&CK T1547.001 registry Run key persistence by analyzing Sysmon Event ID 13 logs and registry queries to identify malicious auto-start entries.
- [[analyzing-persistence-mechanisms-in-linux]] *(similar)* — Detect and analyze Linux persistence mechanisms including crontab entries, systemd service units, LD_PRELOAD hijacking, bashrc modifications, and authorized_keys backdoors using auditd and file integrity monitoring
- [[deploying-ransomware-canary-files]] *(similar)* — Deploys and monitors ransomware canary files across critical directories using Python's watchdog library for real-time filesystem event detection. Places strategically named decoy files that mimic high-value targets (financial records, credentials, database exports) in locations ransomware typically
- [[detecting-malicious-scheduled-tasks-with-sysmon]] *(similar)* — Detect malicious scheduled task creation and modification using Sysmon Event IDs 1 (Process Create for schtasks.exe), 11 (File Create for task XML), and Windows Security Event 4698/4702. The analyst correlates task creation with suspicious parent processes, public directory paths, and encoded comman
- [[hunting-bootkits-in-efi-system-partition]] *(similar)* — Baseline the EFI System Partition and hunt malicious EFI binaries (ESPecter, BlackLotus, Bootkitty, Glupteba) by mounting the ESP, hashing and verifying boot loaders, scanning with YARA, and detecting anomalous non-EFI files.
- [[hunting-for-data-staging-before-exfiltration]] *(similar)* — Detect data staging activity before exfiltration by monitoring for archive creation with 7-Zip/RAR, unusual temp folder access, large file consolidation, and staging directory patterns via EDR and process telemetry

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
