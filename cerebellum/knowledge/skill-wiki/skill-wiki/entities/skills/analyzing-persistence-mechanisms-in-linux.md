---
title: analyzing-persistence-mechanisms-in-linux
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-kubernetes-audit-logs, analyzing-linux-audit-logs-for-intrusion, analyzing-linux-kernel-rootkits, analyzing-linux-system-artifacts, detecting-container-drift-at-runtime, detecting-wmi-persistence, hunting-bootkits-in-efi-system-partition, hunting-for-startup-folder-persistence, implementing-file-integrity-monitoring-with-aide]
confidence: low
---

Detect and analyze Linux persistence mechanisms including crontab entries, systemd service units, LD_PRELOAD hijacking, bashrc modifications, and authorized_keys backdoors using auditd and file integrity monitoring

## Metadata

- **ID:** `analyzing-persistence-mechanisms-in-linux`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/analyzing-persistence-mechanisms-in-linux/SKILL.md`
- **Score:** 27.0
- **Edges:** 9

## Related Skills

- [[analyzing-kubernetes-audit-logs]] *(similar)* — Parses Kubernetes API server audit logs (JSON lines) to detect exec-into-pod, secret access, RBAC modifications, privileged pod creation, and anonymous API access. Builds threat detection rules from audit event patterns. Use when investigating Kubernetes cluster compromise or building k8s-specific S
- [[detecting-container-drift-at-runtime]] *(similar)* — Detect unauthorized modifications to running containers by monitoring for binary execution drift, file system changes, and configuration deviations from the original container image.
- [[detecting-wmi-persistence]] *(similar)* — Detect WMI event subscription persistence by analyzing Sysmon Event IDs 19, 20, and 21 for malicious EventFilter, EventConsumer, and FilterToConsumerBinding creation.
- [[hunting-for-startup-folder-persistence]] *(similar)* — Detect T1547.001 startup folder persistence by monitoring Windows startup directories for suspicious file creation, analyzing autoruns entries, and using Python watchdog for real-time filesystem monitoring.
- [[implementing-file-integrity-monitoring-with-aide]] *(similar)* — Configure AIDE (Advanced Intrusion Detection Environment) for file integrity monitoring including baseline creation, scheduled integrity checks, change detection, and alerting
- [[analyzing-linux-audit-logs-for-intrusion]] *(complement)* — Uses the Linux Audit framework (auditd) with ausearch and aureport utilities to detect intrusion attempts, unauthorized access, privilege escalation, and suspicious system activity. Covers audit rule configuration, log querying, timeline reconstruction, and integration with SIEM platforms. Activates
- [[analyzing-linux-system-artifacts]] *(complement)* — Examine Linux system artifacts including auth logs, cron jobs, shell history, and system configuration to uncover evidence of compromise or unauthorized activity.
- [[analyzing-linux-kernel-rootkits]] *(similar)* — Detect kernel-level rootkits in Linux memory dumps using Volatility3 linux plugins (check_syscall, lsmod, hidden_modules), rkhunter system scanning, and /proc vs /sys discrepancy analysis to identify hooked syscalls, hidden kernel modules, and tampered system structures.
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
