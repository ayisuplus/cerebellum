---
title: detecting-living-off-the-land-attacks
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-powershell-empire-artifacts, analyzing-powershell-script-block-logging, analyzing-windows-prefetch-with-python, analyzing-windows-shellbag-artifacts, detecting-container-escape-attempts, detecting-credential-dumping-techniques, detecting-evasion-techniques-in-endpoint-logs, detecting-malicious-scheduled-tasks-with-sysmon, detecting-mimikatz-execution-patterns, detecting-pass-the-hash-attacks, detecting-process-hollowing-technique, detecting-ransomware-encryption-behavior, detecting-service-account-abuse, detecting-wmi-persistence, hunting-for-ntlm-relay-attacks, hunting-for-registry-run-key-persistence, hunting-for-startup-folder-persistence, hunting-for-unusual-service-installations, implementing-ransomware-kill-switch-detection]
confidence: medium
---

Detect abuse of legitimate Windows binaries (LOLBins) used for living off the land attacks. Monitors process creation, command-line arguments, and parent-child relationships to identify suspicious LOLBin execution patterns.

## Metadata

- **ID:** `detecting-living-off-the-land-attacks`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-living-off-the-land-attacks/SKILL.md`
- **Score:** 48.0
- **Edges:** 19

## Related Skills

- [[detecting-mimikatz-execution-patterns]] *(complement)* — Detect Mimikatz execution through command-line patterns, LSASS access signatures, binary indicators, and in-memory detection of known modules.
- [[detecting-credential-dumping-techniques]] *(similar)* — Detect LSASS credential dumping, SAM database extraction, and NTDS.dit theft using Sysmon Event ID 10, Windows Security logs, and SIEM correlation rules
- [[detecting-malicious-scheduled-tasks-with-sysmon]] *(similar)* — Detect malicious scheduled task creation and modification using Sysmon Event IDs 1 (Process Create for schtasks.exe), 11 (File Create for task XML), and Windows Security Event 4698/4702. The analyst correlates task creation with suspicious parent processes, public directory paths, and encoded comman
- [[detecting-pass-the-hash-attacks]] *(similar)* — Detect Pass-the-Hash attacks by analyzing NTLM authentication patterns, identifying Type 3 logons with NTLM where Kerberos is expected, and correlating with credential dumping.
- [[detecting-service-account-abuse]] *(similar)* — Detect abuse of service accounts through anomalous interactive logons, privilege escalation, lateral movement, and unauthorized access patterns.
- [[analyzing-powershell-empire-artifacts]] *(similar)* — Detect PowerShell Empire framework artifacts in Windows event logs by identifying Base64 encoded launcher patterns, default user agents, staging URL structures, stager IOCs, and known Empire module signatures in Script Block Logging events.
- [[analyzing-powershell-script-block-logging]] *(similar)* — Parse Windows PowerShell Script Block Logs (Event ID 4104) from EVTX files to detect obfuscated commands, encoded payloads, and living-off-the-land techniques. Uses python-evtx to extract and reconstruct multi-block scripts, applies entropy analysis and pattern matching for Base64-encoded commands, 
- [[analyzing-windows-prefetch-with-python]] *(similar)* — Parse Windows Prefetch files using the windowsprefetch Python library to reconstruct application execution history, detect renamed or masquerading binaries, and identify suspicious program execution patterns.
- [[analyzing-windows-shellbag-artifacts]] *(similar)* — Analyze Windows Shellbag registry artifacts to reconstruct folder browsing activity, detect access to removable media and network shares, and establish user interaction with directories even after deletion using SBECmd and ShellBags Explorer.
- [[detecting-container-escape-attempts]] *(similar)* — Container escape is a critical attack technique where an adversary breaks out of container isolation to access the host system or other containers. Detection involves monitoring for escape indicators
- [[detecting-evasion-techniques-in-endpoint-logs]] *(similar)* — Detects defense evasion techniques used by adversaries in endpoint logs including log tampering, timestomping, process injection, and security tool disabling. Use when investigating suspicious endpoint behavior, building detection rules for evasion tactics, or conducting threat hunting for stealthy 
- [[detecting-process-hollowing-technique]] *(similar)* — Detect process hollowing (T1055.012) by analyzing memory-mapped sections, hollowed process indicators, and parent-child process anomalies in EDR telemetry.
- [[detecting-ransomware-encryption-behavior]] *(similar)* — Detects ransomware encryption activity in real time using entropy analysis, file system I/O monitoring, and behavioral heuristics. Identifies mass file modification patterns, abnormal entropy spikes in written data, and suspicious process behavior characteristic of ransomware encryption routines. Ac
- [[detecting-wmi-persistence]] *(similar)* — Detect WMI event subscription persistence by analyzing Sysmon Event IDs 19, 20, and 21 for malicious EventFilter, EventConsumer, and FilterToConsumerBinding creation.
- [[hunting-for-ntlm-relay-attacks]] *(similar)* — Detect NTLM relay attacks by analyzing Windows Event 4624 logon type 3 with NTLMSSP authentication, identifying IP-to-hostname mismatches, Responder traffic signatures, SMB signing status, and suspicious authentication patterns across the domain.
- [[hunting-for-registry-run-key-persistence]] *(similar)* — Detect MITRE ATT&CK T1547.001 registry Run key persistence by analyzing Sysmon Event ID 13 logs and registry queries to identify malicious auto-start entries.
- [[hunting-for-startup-folder-persistence]] *(similar)* — Detect T1547.001 startup folder persistence by monitoring Windows startup directories for suspicious file creation, analyzing autoruns entries, and using Python watchdog for real-time filesystem monitoring.
- [[hunting-for-unusual-service-installations]] *(similar)* — Detect suspicious Windows service installations (MITRE ATT&CK T1543.003) by parsing System event logs for Event ID 7045, analyzing service binary paths, and identifying indicators of persistence mechanisms.
- [[implementing-ransomware-kill-switch-detection]] *(similar)* — Detects and exploits ransomware kill switch mechanisms including mutex-based execution guards, domain-based kill switches, and registry-based termination checks. Implements proactive mutex vaccination and kill switch domain monitoring to prevent ransomware from executing. Activates for requests invo

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
