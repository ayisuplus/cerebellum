---
title: implementing-siem-correlation-rules-for-apt
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-security-logs-with-splunk, building-detection-rule-with-splunk-spl, building-detection-rules-with-sigma, configuring-windows-event-logging-for-detection, correlating-security-events-in-qradar, detecting-azure-lateral-movement, detecting-credential-dumping-techniques, detecting-lateral-movement-with-zeek, detecting-malicious-scheduled-tasks-with-sysmon, detecting-pass-the-hash-attacks, extracting-windows-event-logs-artifacts, hunting-for-ntlm-relay-attacks, implementing-siem-use-case-tuning, implementing-siem-use-cases-for-detection, performing-false-positive-reduction-in-siem, performing-threat-hunting-with-elastic-siem, triaging-security-alerts-in-splunk]
confidence: medium
---

Write multi-event correlation rules that detect APT lateral movement by chaining Windows authentication events, process execution telemetry, and network connection logs across hosts. Uses Splunk SPL and Sigma rule format to correlate Event IDs 4624, 4648, 4688, and Sysmon Events 1/3 within sliding t

## Metadata

- **ID:** `implementing-siem-correlation-rules-for-apt`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/implementing-siem-correlation-rules-for-apt/SKILL.md`
- **Score:** 40.0
- **Edges:** 17

## Related Skills

- [[detecting-azure-lateral-movement]] *(similar)* — Detect lateral movement in Azure AD/Entra ID environments using Microsoft Graph API audit logs, Azure Sentinel KQL hunting queries, and sign-in anomaly correlation to identify privilege escalation, token theft, and cross-tenant pivoting.
- [[detecting-lateral-movement-with-zeek]] *(similar)* — Detect lateral movement in network traffic using Zeek (formerly Bro) log analysis. Parses conn.log, smb_mapping.log, smb_files.log, dce_rpc.log, kerberos.log, and ntlm.log to identify SMB file transfers, NTLM account spray activity, remote service execution, and anomalous internal connections.

- [[detecting-pass-the-hash-attacks]] *(similar)* — Detect Pass-the-Hash attacks by analyzing NTLM authentication patterns, identifying Type 3 logons with NTLM where Kerberos is expected, and correlating with credential dumping.
- [[implementing-siem-use-case-tuning]] *(similar)* — Tune SIEM detection rules to reduce false positives by analyzing alert volumes, creating whitelists, adjusting thresholds, and measuring detection efficacy metrics in Splunk and Elastic
- [[implementing-siem-use-cases-for-detection]] *(similar)* — Implements SIEM detection use cases by designing correlation rules, threshold alerts, and behavioral analytics mapped to MITRE ATT&CK techniques across Splunk, Elastic, and Sentinel. Use when SOC teams need to expand detection coverage, formalize use case lifecycle management, or build a detection l
- [[analyzing-security-logs-with-splunk]] *(similar)* — Leverages Splunk Enterprise Security and SPL (Search Processing Language) to investigate security incidents through log correlation, timeline reconstruction, and anomaly detection. Covers Windows event logs, firewall logs, proxy logs, and authentication data analysis. Activates for requests involvin
- [[building-detection-rule-with-splunk-spl]] *(similar)* — Build effective detection rules using Splunk Search Processing Language (SPL) correlation searches to identify security threats in SOC environments.
- [[building-detection-rules-with-sigma]] *(similar)* — Builds vendor-agnostic detection rules using the Sigma rule format for threat detection across SIEM platforms including Splunk, Elastic, and Microsoft Sentinel. Use when creating portable detection logic from threat intelligence, mapping rules to MITRE ATT&CK techniques, or converting community Sigm
- [[configuring-windows-event-logging-for-detection]] *(similar)* — Configures Windows Event Logging with advanced audit policies to generate high-fidelity security events for threat detection and forensic investigation. Use when enabling audit policies for logon events, process creation, privilege use, and object access to feed SIEM detection rules. Activates for r
- [[correlating-security-events-in-qradar]] *(similar)* — Correlates security events in IBM QRadar SIEM using AQL (Ariel Query Language), custom rules, building blocks, and offense management to detect multi-stage attacks across network, endpoint, and application log sources. Use when SOC analysts need to investigate QRadar offenses, build correlation rule
- [[detecting-credential-dumping-techniques]] *(similar)* — Detect LSASS credential dumping, SAM database extraction, and NTDS.dit theft using Sysmon Event ID 10, Windows Security logs, and SIEM correlation rules
- [[detecting-malicious-scheduled-tasks-with-sysmon]] *(similar)* — Detect malicious scheduled task creation and modification using Sysmon Event IDs 1 (Process Create for schtasks.exe), 11 (File Create for task XML), and Windows Security Event 4698/4702. The analyst correlates task creation with suspicious parent processes, public directory paths, and encoded comman
- [[extracting-windows-event-logs-artifacts]] *(similar)* — Extract, parse, and analyze Windows Event Logs (EVTX) using Chainsaw, Hayabusa, and EvtxECmd to detect lateral movement, persistence, and privilege escalation.
- [[hunting-for-ntlm-relay-attacks]] *(similar)* — Detect NTLM relay attacks by analyzing Windows Event 4624 logon type 3 with NTLMSSP authentication, identifying IP-to-hostname mismatches, Responder traffic signatures, SMB signing status, and suspicious authentication patterns across the domain.
- [[performing-false-positive-reduction-in-siem]] *(similar)* — Perform systematic SIEM false positive reduction through rule tuning, threshold adjustment, correlation refinement, and threat intelligence enrichment to combat alert fatigue.
- [[performing-threat-hunting-with-elastic-siem]] *(similar)* — Performs proactive threat hunting in Elastic Security SIEM using KQL/EQL queries, detection rules, and Timeline investigation to identify threats that evade automated detection. Use when SOC teams need to hunt for specific ATT&CK techniques, investigate anomalous behaviors, or validate detection cov
- [[triaging-security-alerts-in-splunk]] *(similar)* — Triages security alerts in Splunk Enterprise Security by classifying severity, investigating notable events, correlating related telemetry, and making escalation or closure decisions using SPL queries and the Incident Review dashboard. Use when SOC analysts face queued alerts from correlation search

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
