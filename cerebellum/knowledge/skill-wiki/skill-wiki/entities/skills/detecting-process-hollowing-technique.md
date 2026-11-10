---
title: detecting-process-hollowing-technique
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [detecting-credential-dumping-techniques, detecting-evasion-techniques-in-endpoint-logs, detecting-living-off-the-land-attacks, detecting-malicious-scheduled-tasks-with-sysmon, detecting-mimikatz-execution-patterns, hunting-for-data-staging-before-exfiltration]
confidence: low
---

Detect process hollowing (T1055.012) by analyzing memory-mapped sections, hollowed process indicators, and parent-child process anomalies in EDR telemetry.

## Metadata

- **ID:** `detecting-process-hollowing-technique`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-process-hollowing-technique/SKILL.md`
- **Score:** 31.0
- **Edges:** 6

## Related Skills

- [[detecting-credential-dumping-techniques]] *(similar)* — Detect LSASS credential dumping, SAM database extraction, and NTDS.dit theft using Sysmon Event ID 10, Windows Security logs, and SIEM correlation rules
- [[detecting-evasion-techniques-in-endpoint-logs]] *(similar)* — Detects defense evasion techniques used by adversaries in endpoint logs including log tampering, timestomping, process injection, and security tool disabling. Use when investigating suspicious endpoint behavior, building detection rules for evasion tactics, or conducting threat hunting for stealthy 
- [[detecting-living-off-the-land-attacks]] *(similar)* — Detect abuse of legitimate Windows binaries (LOLBins) used for living off the land attacks. Monitors process creation, command-line arguments, and parent-child relationships to identify suspicious LOLBin execution patterns.

- [[detecting-malicious-scheduled-tasks-with-sysmon]] *(similar)* — Detect malicious scheduled task creation and modification using Sysmon Event IDs 1 (Process Create for schtasks.exe), 11 (File Create for task XML), and Windows Security Event 4698/4702. The analyst correlates task creation with suspicious parent processes, public directory paths, and encoded comman
- [[detecting-mimikatz-execution-patterns]] *(similar)* — Detect Mimikatz execution through command-line patterns, LSASS access signatures, binary indicators, and in-memory detection of known modules.
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
