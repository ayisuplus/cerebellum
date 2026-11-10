---
title: hunting-for-data-staging-before-exfiltration
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [detecting-process-hollowing-technique, detecting-ransomware-precursors-in-network, hunting-for-startup-folder-persistence, hunting-for-unusual-network-connections, hunting-for-unusual-service-installations]
confidence: low
---

Detect data staging activity before exfiltration by monitoring for archive creation with 7-Zip/RAR, unusual temp folder access, large file consolidation, and staging directory patterns via EDR and process telemetry

## Metadata

- **ID:** `hunting-for-data-staging-before-exfiltration`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/hunting-for-data-staging-before-exfiltration/SKILL.md`
- **Score:** 27.0
- **Edges:** 5

## Related Skills

- [[detecting-process-hollowing-technique]] *(similar)* — Detect process hollowing (T1055.012) by analyzing memory-mapped sections, hollowed process indicators, and parent-child process anomalies in EDR telemetry.
- [[detecting-ransomware-precursors-in-network]] *(similar)* — Detects early-stage ransomware indicators in network traffic before encryption begins, including initial access broker activity, command-and-control beaconing, credential harvesting, reconnaissance scanning, and staging behavior. Uses network detection tools (Zeek, Suricata, Arkime), SIEM correlatio
- [[hunting-for-startup-folder-persistence]] *(similar)* — Detect T1547.001 startup folder persistence by monitoring Windows startup directories for suspicious file creation, analyzing autoruns entries, and using Python watchdog for real-time filesystem monitoring.
- [[hunting-for-unusual-network-connections]] *(similar)* — Hunt for unusual network connections by analyzing outbound traffic patterns, rare destinations, non-standard ports, and anomalous connection frequencies from endpoints.
- [[hunting-for-unusual-service-installations]] *(similar)* — Detect suspicious Windows service installations (MITRE ATT&CK T1543.003) by parsing System event logs for Event ID 7045, analyzing service binary paths, and identifying indicators of persistence mechanisms.

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
