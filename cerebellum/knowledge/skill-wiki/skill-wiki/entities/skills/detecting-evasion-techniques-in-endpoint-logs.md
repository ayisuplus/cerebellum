---
title: detecting-evasion-techniques-in-endpoint-logs
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [detecting-container-escape-attempts, detecting-credential-dumping-techniques, detecting-living-off-the-land-attacks, detecting-mimikatz-execution-patterns, detecting-process-hollowing-technique, detecting-service-account-abuse, detecting-stuxnet-style-attacks, hunting-for-spearphishing-indicators, performing-threat-hunting-with-elastic-siem]
confidence: low
---

Detects defense evasion techniques used by adversaries in endpoint logs including log tampering, timestomping, process injection, and security tool disabling. Use when investigating suspicious endpoint behavior, building detection rules for evasion tactics, or conducting threat hunting for stealthy

## Metadata

- **ID:** `detecting-evasion-techniques-in-endpoint-logs`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-evasion-techniques-in-endpoint-logs/SKILL.md`
- **Score:** 36.0
- **Edges:** 9

## Related Skills

- [[detecting-credential-dumping-techniques]] *(similar)* — Detect LSASS credential dumping, SAM database extraction, and NTDS.dit theft using Sysmon Event ID 10, Windows Security logs, and SIEM correlation rules
- [[detecting-living-off-the-land-attacks]] *(similar)* — Detect abuse of legitimate Windows binaries (LOLBins) used for living off the land attacks. Monitors process creation, command-line arguments, and parent-child relationships to identify suspicious LOLBin execution patterns.

- [[detecting-mimikatz-execution-patterns]] *(similar)* — Detect Mimikatz execution through command-line patterns, LSASS access signatures, binary indicators, and in-memory detection of known modules.
- [[detecting-service-account-abuse]] *(similar)* — Detect abuse of service accounts through anomalous interactive logons, privilege escalation, lateral movement, and unauthorized access patterns.
- [[performing-threat-hunting-with-elastic-siem]] *(similar)* — Performs proactive threat hunting in Elastic Security SIEM using KQL/EQL queries, detection rules, and Timeline investigation to identify threats that evade automated detection. Use when SOC teams need to hunt for specific ATT&CK techniques, investigate anomalous behaviors, or validate detection cov
- [[detecting-container-escape-attempts]] *(similar)* — Container escape is a critical attack technique where an adversary breaks out of container isolation to access the host system or other containers. Detection involves monitoring for escape indicators
- [[detecting-process-hollowing-technique]] *(similar)* — Detect process hollowing (T1055.012) by analyzing memory-mapped sections, hollowed process indicators, and parent-child process anomalies in EDR telemetry.
- [[detecting-stuxnet-style-attacks]] *(similar)* — This skill covers detecting sophisticated cyber-physical attacks that follow the Stuxnet attack pattern of modifying PLC logic while spoofing sensor readings to hide the manipulation from operators. It addresses PLC logic integrity monitoring, physics-based process anomaly detection, engineering wor
- [[hunting-for-spearphishing-indicators]] *(similar)* — Hunt for spearphishing campaign indicators across email logs, endpoint telemetry, and network data to detect targeted email attacks.

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
