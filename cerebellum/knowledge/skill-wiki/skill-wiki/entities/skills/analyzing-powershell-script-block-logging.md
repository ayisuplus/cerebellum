---
title: analyzing-powershell-script-block-logging
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-powershell-empire-artifacts, analyzing-security-logs-with-splunk, analyzing-usb-device-connection-history, analyzing-windows-prefetch-with-python, analyzing-windows-shellbag-artifacts, building-super-timelines-with-plaso, detecting-living-off-the-land-attacks, detecting-malicious-scheduled-tasks-with-sysmon, extracting-windows-event-logs-artifacts, hunting-evtx-with-chainsaw, performing-firmware-extraction-with-binwalk]
confidence: low
---

Parse Windows PowerShell Script Block Logs (Event ID 4104) from EVTX files to detect obfuscated commands, encoded payloads, and living-off-the-land techniques. Uses python-evtx to extract and reconstruct multi-block scripts, applies entropy analysis and pattern matching for Base64-encoded commands,

## Metadata

- **ID:** `analyzing-powershell-script-block-logging`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/analyzing-powershell-script-block-logging/SKILL.md`
- **Score:** 37.0
- **Edges:** 11

## Related Skills

- [[analyzing-windows-prefetch-with-python]] *(complement)* — Parse Windows Prefetch files using the windowsprefetch Python library to reconstruct application execution history, detect renamed or masquerading binaries, and identify suspicious program execution patterns.
- [[detecting-living-off-the-land-attacks]] *(similar)* — Detect abuse of legitimate Windows binaries (LOLBins) used for living off the land attacks. Monitors process creation, command-line arguments, and parent-child relationships to identify suspicious LOLBin execution patterns.

- [[detecting-malicious-scheduled-tasks-with-sysmon]] *(similar)* — Detect malicious scheduled task creation and modification using Sysmon Event IDs 1 (Process Create for schtasks.exe), 11 (File Create for task XML), and Windows Security Event 4698/4702. The analyst correlates task creation with suspicious parent processes, public directory paths, and encoded comman
- [[extracting-windows-event-logs-artifacts]] *(similar)* — Extract, parse, and analyze Windows Event Logs (EVTX) using Chainsaw, Hayabusa, and EvtxECmd to detect lateral movement, persistence, and privilege escalation.
- [[hunting-evtx-with-chainsaw]] *(similar)* — Perform rapid Sigma and keyword hunting across Windows event logs with Chainsaw.
- [[analyzing-powershell-empire-artifacts]] *(complement)* — Detect PowerShell Empire framework artifacts in Windows event logs by identifying Base64 encoded launcher patterns, default user agents, staging URL structures, stager IOCs, and known Empire module signatures in Script Block Logging events.
- [[analyzing-security-logs-with-splunk]] *(similar)* — Leverages Splunk Enterprise Security and SPL (Search Processing Language) to investigate security incidents through log correlation, timeline reconstruction, and anomaly detection. Covers Windows event logs, firewall logs, proxy logs, and authentication data analysis. Activates for requests involvin
- [[analyzing-usb-device-connection-history]] *(similar)* — Investigate USB device connection history from Windows registry, event logs, and setupapi logs to track removable media usage and potential data exfiltration.
- [[analyzing-windows-shellbag-artifacts]] *(similar)* — Analyze Windows Shellbag registry artifacts to reconstruct folder browsing activity, detect access to removable media and network shares, and establish user interaction with directories even after deletion using SBECmd and ShellBags Explorer.
- [[building-super-timelines-with-plaso]] *(similar)* — Generate log2timeline and Plaso super-timelines and triage them in Timesketch.
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
