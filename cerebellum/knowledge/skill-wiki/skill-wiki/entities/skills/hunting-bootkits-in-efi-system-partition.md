---
title: hunting-bootkits-in-efi-system-partition
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-linux-kernel-rootkits, analyzing-persistence-mechanisms-in-linux, hunting-for-registry-run-key-persistence, hunting-for-startup-folder-persistence, hunting-for-unusual-service-installations, performing-firmware-extraction-with-binwalk]
confidence: low
---

Baseline the EFI System Partition and hunt malicious EFI binaries (ESPecter, BlackLotus, Bootkitty, Glupteba) by mounting the ESP, hashing and verifying boot loaders, scanning with YARA, and detecting anomalous non-EFI files.

## Metadata

- **ID:** `hunting-bootkits-in-efi-system-partition`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/hunting-bootkits-in-efi-system-partition/SKILL.md`
- **Score:** 38.0
- **Edges:** 6

## Related Skills

- [[analyzing-persistence-mechanisms-in-linux]] *(similar)* — Detect and analyze Linux persistence mechanisms including crontab entries, systemd service units, LD_PRELOAD hijacking, bashrc modifications, and authorized_keys backdoors using auditd and file integrity monitoring
- [[hunting-for-registry-run-key-persistence]] *(similar)* — Detect MITRE ATT&CK T1547.001 registry Run key persistence by analyzing Sysmon Event ID 13 logs and registry queries to identify malicious auto-start entries.
- [[hunting-for-startup-folder-persistence]] *(similar)* — Detect T1547.001 startup folder persistence by monitoring Windows startup directories for suspicious file creation, analyzing autoruns entries, and using Python watchdog for real-time filesystem monitoring.
- [[hunting-for-unusual-service-installations]] *(similar)* — Detect suspicious Windows service installations (MITRE ATT&CK T1543.003) by parsing System event logs for Event ID 7045, analyzing service binary paths, and identifying indicators of persistence mechanisms.
- [[performing-firmware-extraction-with-binwalk]] *(similar)* — Performs firmware image extraction and analysis using binwalk to identify embedded filesystems, compressed archives, bootloaders, kernel images, and cryptographic material. Covers entropy analysis for detecting encrypted or compressed regions, recursive extraction of nested archives, SquashFS/CramFS
- [[analyzing-linux-kernel-rootkits]] *(similar)* — Detect kernel-level rootkits in Linux memory dumps using Volatility3 linux plugins (check_syscall, lsmod, hidden_modules), rkhunter system scanning, and /proc vs /sys discrepancy analysis to identify hooked syscalls, hidden kernel modules, and tampered system structures.

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
