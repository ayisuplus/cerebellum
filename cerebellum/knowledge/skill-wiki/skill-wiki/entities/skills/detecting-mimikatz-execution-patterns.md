---
title: detecting-mimikatz-execution-patterns
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-linux-kernel-rootkits, analyzing-powershell-empire-artifacts, analyzing-windows-prefetch-with-python, detecting-credential-dumping-techniques, detecting-evasion-techniques-in-endpoint-logs, detecting-living-off-the-land-attacks, detecting-pass-the-hash-attacks, detecting-process-hollowing-technique, detecting-ransomware-encryption-behavior, detecting-rdp-brute-force-attacks, detecting-service-account-abuse, detecting-wmi-persistence, hunting-for-command-and-control-beaconing, implementing-ransomware-kill-switch-detection, performing-purple-team-atomic-testing]
confidence: low
---

Detect Mimikatz execution through command-line patterns, LSASS access signatures, binary indicators, and in-memory detection of known modules.

## Metadata

- **ID:** `detecting-mimikatz-execution-patterns`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-mimikatz-execution-patterns/SKILL.md`
- **Score:** 31.0
- **Edges:** 15

## Related Skills

- [[detecting-pass-the-hash-attacks]] *(complement)* — Detect Pass-the-Hash attacks by analyzing NTLM authentication patterns, identifying Type 3 logons with NTLM where Kerberos is expected, and correlating with credential dumping.
- [[detecting-rdp-brute-force-attacks]] *(similar)* — Detect RDP brute force attacks by analyzing Windows Security Event Logs for failed authentication patterns (Event ID 4625), successful logons after failures (Event ID 4624), NLA failures, and source IP frequency analysis.
- [[detecting-service-account-abuse]] *(similar)* — Detect abuse of service accounts through anomalous interactive logons, privilege escalation, lateral movement, and unauthorized access patterns.
- [[detecting-wmi-persistence]] *(similar)* — Detect WMI event subscription persistence by analyzing Sysmon Event IDs 19, 20, and 21 for malicious EventFilter, EventConsumer, and FilterToConsumerBinding creation.
- [[hunting-for-command-and-control-beaconing]] *(similar)* — Detect C2 beaconing patterns in network traffic using frequency analysis, jitter detection, and domain reputation to identify compromised endpoints communicating with adversary infrastructure.
- [[detecting-living-off-the-land-attacks]] *(complement)* — Detect abuse of legitimate Windows binaries (LOLBins) used for living off the land attacks. Monitors process creation, command-line arguments, and parent-child relationships to identify suspicious LOLBin execution patterns.

- [[analyzing-linux-kernel-rootkits]] *(similar)* — Detect kernel-level rootkits in Linux memory dumps using Volatility3 linux plugins (check_syscall, lsmod, hidden_modules), rkhunter system scanning, and /proc vs /sys discrepancy analysis to identify hooked syscalls, hidden kernel modules, and tampered system structures.
- [[analyzing-powershell-empire-artifacts]] *(similar)* — Detect PowerShell Empire framework artifacts in Windows event logs by identifying Base64 encoded launcher patterns, default user agents, staging URL structures, stager IOCs, and known Empire module signatures in Script Block Logging events.
- [[analyzing-windows-prefetch-with-python]] *(similar)* — Parse Windows Prefetch files using the windowsprefetch Python library to reconstruct application execution history, detect renamed or masquerading binaries, and identify suspicious program execution patterns.
- [[detecting-credential-dumping-techniques]] *(similar)* — Detect LSASS credential dumping, SAM database extraction, and NTDS.dit theft using Sysmon Event ID 10, Windows Security logs, and SIEM correlation rules
- [[detecting-evasion-techniques-in-endpoint-logs]] *(similar)* — Detects defense evasion techniques used by adversaries in endpoint logs including log tampering, timestomping, process injection, and security tool disabling. Use when investigating suspicious endpoint behavior, building detection rules for evasion tactics, or conducting threat hunting for stealthy 
- [[detecting-process-hollowing-technique]] *(similar)* — Detect process hollowing (T1055.012) by analyzing memory-mapped sections, hollowed process indicators, and parent-child process anomalies in EDR telemetry.
- [[detecting-ransomware-encryption-behavior]] *(similar)* — Detects ransomware encryption activity in real time using entropy analysis, file system I/O monitoring, and behavioral heuristics. Identifies mass file modification patterns, abnormal entropy spikes in written data, and suspicious process behavior characteristic of ransomware encryption routines. Ac
- [[implementing-ransomware-kill-switch-detection]] *(similar)* — Detects and exploits ransomware kill switch mechanisms including mutex-based execution guards, domain-based kill switches, and registry-based termination checks. Implements proactive mutex vaccination and kill switch domain monitoring to prevent ransomware from executing. Activates for requests invo
- [[performing-purple-team-atomic-testing]] *(similar)* — Executes Atomic Red Team tests mapped to MITRE ATT&CK techniques, performs coverage gap analysis across the ATT&CK matrix, and runs detection validation loops to measure blue team visibility. Covers Invoke-AtomicRedTeam PowerShell execution, ATT&CK Navigator layer generation for heatmaps, Sigma rule

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
