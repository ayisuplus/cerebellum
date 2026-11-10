---
title: analyzing-linux-kernel-rootkits
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-linux-audit-logs-for-intrusion, analyzing-linux-system-artifacts, analyzing-persistence-mechanisms-in-linux, detecting-mimikatz-execution-patterns, hunting-bootkits-in-efi-system-partition, performing-firmware-extraction-with-binwalk]
confidence: low
---

Detect kernel-level rootkits in Linux memory dumps using Volatility3 linux plugins (check_syscall, lsmod, hidden_modules), rkhunter system scanning, and /proc vs /sys discrepancy analysis to identify hooked syscalls, hidden kernel modules, and tampered system structures.

## Metadata

- **ID:** `analyzing-linux-kernel-rootkits`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/analyzing-linux-kernel-rootkits/SKILL.md`
- **Score:** 35.0
- **Edges:** 6

## Related Skills

- [[analyzing-linux-audit-logs-for-intrusion]] *(similar)* — Uses the Linux Audit framework (auditd) with ausearch and aureport utilities to detect intrusion attempts, unauthorized access, privilege escalation, and suspicious system activity. Covers audit rule configuration, log querying, timeline reconstruction, and integration with SIEM platforms. Activates
- [[analyzing-linux-system-artifacts]] *(similar)* — Examine Linux system artifacts including auth logs, cron jobs, shell history, and system configuration to uncover evidence of compromise or unauthorized activity.
- [[analyzing-persistence-mechanisms-in-linux]] *(similar)* — Detect and analyze Linux persistence mechanisms including crontab entries, systemd service units, LD_PRELOAD hijacking, bashrc modifications, and authorized_keys backdoors using auditd and file integrity monitoring
- [[detecting-mimikatz-execution-patterns]] *(similar)* — Detect Mimikatz execution through command-line patterns, LSASS access signatures, binary indicators, and in-memory detection of known modules.
- [[hunting-bootkits-in-efi-system-partition]] *(similar)* — Baseline the EFI System Partition and hunt malicious EFI binaries (ESPecter, BlackLotus, Bootkitty, Glupteba) by mounting the ESP, hashing and verifying boot loaders, scanning with YARA, and detecting anomalous non-EFI files.
- [[performing-firmware-extraction-with-binwalk]] *(similar)* — Performs firmware image extraction and analysis using binwalk to identify embedded filesystems, compressed archives, bootloaders, kernel images, and cryptographic material. Covers entropy analysis for detecting encrypted or compressed regions, recursive extraction of nested archives, SquashFS/CramFS

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
