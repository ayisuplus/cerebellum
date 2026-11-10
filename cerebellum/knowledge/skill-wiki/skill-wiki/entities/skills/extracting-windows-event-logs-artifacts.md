---
title: extracting-windows-event-logs-artifacts
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-linux-system-artifacts, analyzing-powershell-empire-artifacts, analyzing-powershell-script-block-logging, analyzing-usb-device-connection-history, analyzing-windows-prefetch-with-python, analyzing-windows-shellbag-artifacts, building-super-timelines-with-plaso, detecting-azure-lateral-movement, detecting-credential-dumping-techniques, detecting-wmi-persistence, hunting-evtx-with-chainsaw, hunting-for-unusual-service-installations, implementing-siem-correlation-rules-for-apt]
confidence: low
---

Extract, parse, and analyze Windows Event Logs (EVTX) using Chainsaw, Hayabusa, and EvtxECmd to detect lateral movement, persistence, and privilege escalation.

## Metadata

- **ID:** `extracting-windows-event-logs-artifacts`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/extracting-windows-event-logs-artifacts/SKILL.md`
- **Score:** 39.0
- **Edges:** 13

## Related Skills

- [[hunting-evtx-with-chainsaw]] *(complement)* — Perform rapid Sigma and keyword hunting across Windows event logs with Chainsaw.
- [[detecting-azure-lateral-movement]] *(similar)* — Detect lateral movement in Azure AD/Entra ID environments using Microsoft Graph API audit logs, Azure Sentinel KQL hunting queries, and sign-in anomaly correlation to identify privilege escalation, token theft, and cross-tenant pivoting.
- [[detecting-credential-dumping-techniques]] *(similar)* — Detect LSASS credential dumping, SAM database extraction, and NTDS.dit theft using Sysmon Event ID 10, Windows Security logs, and SIEM correlation rules
- [[hunting-for-unusual-service-installations]] *(similar)* — Detect suspicious Windows service installations (MITRE ATT&CK T1543.003) by parsing System event logs for Event ID 7045, analyzing service binary paths, and identifying indicators of persistence mechanisms.
- [[implementing-siem-correlation-rules-for-apt]] *(similar)* — Write multi-event correlation rules that detect APT lateral movement by chaining Windows authentication events, process execution telemetry, and network connection logs across hosts. Uses Splunk SPL and Sigma rule format to correlate Event IDs 4624, 4648, 4688, and Sysmon Events 1/3 within sliding t
- [[analyzing-linux-system-artifacts]] *(similar)* — Examine Linux system artifacts including auth logs, cron jobs, shell history, and system configuration to uncover evidence of compromise or unauthorized activity.
- [[analyzing-powershell-empire-artifacts]] *(similar)* — Detect PowerShell Empire framework artifacts in Windows event logs by identifying Base64 encoded launcher patterns, default user agents, staging URL structures, stager IOCs, and known Empire module signatures in Script Block Logging events.
- [[analyzing-powershell-script-block-logging]] *(similar)* — Parse Windows PowerShell Script Block Logs (Event ID 4104) from EVTX files to detect obfuscated commands, encoded payloads, and living-off-the-land techniques. Uses python-evtx to extract and reconstruct multi-block scripts, applies entropy analysis and pattern matching for Base64-encoded commands, 
- [[analyzing-usb-device-connection-history]] *(similar)* — Investigate USB device connection history from Windows registry, event logs, and setupapi logs to track removable media usage and potential data exfiltration.
- [[analyzing-windows-prefetch-with-python]] *(similar)* — Parse Windows Prefetch files using the windowsprefetch Python library to reconstruct application execution history, detect renamed or masquerading binaries, and identify suspicious program execution patterns.
- [[analyzing-windows-shellbag-artifacts]] *(similar)* — Analyze Windows Shellbag registry artifacts to reconstruct folder browsing activity, detect access to removable media and network shares, and establish user interaction with directories even after deletion using SBECmd and ShellBags Explorer.
- [[building-super-timelines-with-plaso]] *(similar)* — Generate log2timeline and Plaso super-timelines and triage them in Timesketch.
- [[detecting-wmi-persistence]] *(similar)* — Detect WMI event subscription persistence by analyzing Sysmon Event IDs 19, 20, and 21 for malicious EventFilter, EventConsumer, and FilterToConsumerBinding creation.

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
