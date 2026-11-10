---
title: hunting-evtx-with-chainsaw
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-powershell-script-block-logging, building-detection-rules-with-sigma, building-super-timelines-with-plaso, detecting-credential-dumping-techniques, extracting-windows-event-logs-artifacts, hunting-for-ntlm-relay-attacks, hunting-for-spearphishing-indicators, hunting-for-unusual-service-installations]
confidence: low
---

Perform rapid Sigma and keyword hunting across Windows event logs with Chainsaw.

## Metadata

- **ID:** `hunting-evtx-with-chainsaw`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/hunting-evtx-with-chainsaw/SKILL.md`
- **Score:** 33.0
- **Edges:** 8

## Related Skills

- [[building-detection-rules-with-sigma]] *(similar)* — Builds vendor-agnostic detection rules using the Sigma rule format for threat detection across SIEM platforms including Splunk, Elastic, and Microsoft Sentinel. Use when creating portable detection logic from threat intelligence, mapping rules to MITRE ATT&CK techniques, or converting community Sigm
- [[detecting-credential-dumping-techniques]] *(similar)* — Detect LSASS credential dumping, SAM database extraction, and NTDS.dit theft using Sysmon Event ID 10, Windows Security logs, and SIEM correlation rules
- [[hunting-for-ntlm-relay-attacks]] *(similar)* — Detect NTLM relay attacks by analyzing Windows Event 4624 logon type 3 with NTLMSSP authentication, identifying IP-to-hostname mismatches, Responder traffic signatures, SMB signing status, and suspicious authentication patterns across the domain.
- [[hunting-for-spearphishing-indicators]] *(similar)* — Hunt for spearphishing campaign indicators across email logs, endpoint telemetry, and network data to detect targeted email attacks.
- [[hunting-for-unusual-service-installations]] *(similar)* — Detect suspicious Windows service installations (MITRE ATT&CK T1543.003) by parsing System event logs for Event ID 7045, analyzing service binary paths, and identifying indicators of persistence mechanisms.
- [[extracting-windows-event-logs-artifacts]] *(complement)* — Extract, parse, and analyze Windows Event Logs (EVTX) using Chainsaw, Hayabusa, and EvtxECmd to detect lateral movement, persistence, and privilege escalation.
- [[analyzing-powershell-script-block-logging]] *(similar)* — Parse Windows PowerShell Script Block Logs (Event ID 4104) from EVTX files to detect obfuscated commands, encoded payloads, and living-off-the-land techniques. Uses python-evtx to extract and reconstruct multi-block scripts, applies entropy analysis and pattern matching for Base64-encoded commands, 
- [[building-super-timelines-with-plaso]] *(similar)* — Generate log2timeline and Plaso super-timelines and triage them in Timesketch.

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
