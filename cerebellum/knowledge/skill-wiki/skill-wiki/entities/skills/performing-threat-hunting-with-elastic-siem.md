---
title: performing-threat-hunting-with-elastic-siem
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-azure-activity-logs-for-threats, building-cloud-siem-with-sentinel, building-detection-rule-with-splunk-spl, building-detection-rules-with-sigma, building-soc-metrics-and-kpi-tracking, correlating-security-events-in-qradar, detecting-evasion-techniques-in-endpoint-logs, hunting-for-spearphishing-indicators, implementing-endpoint-detection-with-wazuh, implementing-siem-correlation-rules-for-apt, implementing-siem-use-case-tuning, implementing-siem-use-cases-for-detection, investigating-insider-threat-indicators, mapping-mitre-attack-techniques, performing-alert-triage-with-elastic-siem, performing-cloud-native-forensics-with-falco, performing-cloud-native-threat-hunting-with-aws-detective, performing-false-positive-reduction-in-siem, performing-log-source-onboarding-in-siem, performing-purple-team-atomic-testing, performing-user-behavior-analytics, triaging-security-alerts-in-splunk]
confidence: medium
---

Performs proactive threat hunting in Elastic Security SIEM using KQL/EQL queries, detection rules, and Timeline investigation to identify threats that evade automated detection. Use when SOC teams need to hunt for specific ATT&CK techniques, investigate anomalous behaviors, or validate detection cov

## Metadata

- **ID:** `performing-threat-hunting-with-elastic-siem`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/performing-threat-hunting-with-elastic-siem/SKILL.md`
- **Score:** 44.0
- **Edges:** 22

## Related Skills

- [[analyzing-azure-activity-logs-for-threats]] *(similar)* — Queries Azure Monitor activity logs and sign-in logs via azure-monitor-query to detect suspicious administrative operations, impossible travel, privilege escalation, and resource modifications. Builds KQL queries for threat hunting in Azure environments. Use when investigating suspicious Azure tenan
- [[building-detection-rule-with-splunk-spl]] *(similar)* — Build effective detection rules using Splunk Search Processing Language (SPL) correlation searches to identify security threats in SOC environments.
- [[implementing-siem-correlation-rules-for-apt]] *(similar)* — Write multi-event correlation rules that detect APT lateral movement by chaining Windows authentication events, process execution telemetry, and network connection logs across hosts. Uses Splunk SPL and Sigma rule format to correlate Event IDs 4624, 4648, 4688, and Sysmon Events 1/3 within sliding t
- [[performing-user-behavior-analytics]] *(similar)* — Performs User and Entity Behavior Analytics (UEBA) to detect anomalous user activities including impossible travel, unusual access patterns, privilege abuse, and insider threats using SIEM-based behavioral baselines and statistical analysis. Use when SOC teams need to identify compromised accounts o
- [[triaging-security-alerts-in-splunk]] *(similar)* — Triages security alerts in Splunk Enterprise Security by classifying severity, investigating notable events, correlating related telemetry, and making escalation or closure decisions using SPL queries and the Incident Review dashboard. Use when SOC analysts face queued alerts from correlation search
- [[implementing-siem-use-cases-for-detection]] *(complement)* — Implements SIEM detection use cases by designing correlation rules, threshold alerts, and behavioral analytics mapped to MITRE ATT&CK techniques across Splunk, Elastic, and Sentinel. Use when SOC teams need to expand detection coverage, formalize use case lifecycle management, or build a detection l
- [[performing-alert-triage-with-elastic-siem]] *(complement)* — Perform systematic alert triage in Elastic Security SIEM to rapidly classify, prioritize, and investigate security alerts for SOC operations.
- [[building-cloud-siem-with-sentinel]] *(similar)* — This skill covers deploying Microsoft Sentinel as a cloud-native SIEM and SOAR platform for centralized security operations. It details configuring data connectors for multi-cloud log ingestion, writing KQL detection queries, building automated response playbooks with Logic Apps, and leveraging the 
- [[building-detection-rules-with-sigma]] *(similar)* — Builds vendor-agnostic detection rules using the Sigma rule format for threat detection across SIEM platforms including Splunk, Elastic, and Microsoft Sentinel. Use when creating portable detection logic from threat intelligence, mapping rules to MITRE ATT&CK techniques, or converting community Sigm
- [[building-soc-metrics-and-kpi-tracking]] *(similar)* — Builds SOC performance metrics and KPI tracking dashboards measuring Mean Time to Detect (MTTD), Mean Time to Respond (MTTR), alert quality ratios, analyst productivity, and detection coverage using SIEM data. Use when SOC leadership needs operational visibility, continuous improvement tracking, or 
- [[correlating-security-events-in-qradar]] *(similar)* — Correlates security events in IBM QRadar SIEM using AQL (Ariel Query Language), custom rules, building blocks, and offense management to detect multi-stage attacks across network, endpoint, and application log sources. Use when SOC analysts need to investigate QRadar offenses, build correlation rule
- [[detecting-evasion-techniques-in-endpoint-logs]] *(similar)* — Detects defense evasion techniques used by adversaries in endpoint logs including log tampering, timestomping, process injection, and security tool disabling. Use when investigating suspicious endpoint behavior, building detection rules for evasion tactics, or conducting threat hunting for stealthy 
- [[hunting-for-spearphishing-indicators]] *(similar)* — Hunt for spearphishing campaign indicators across email logs, endpoint telemetry, and network data to detect targeted email attacks.
- [[implementing-endpoint-detection-with-wazuh]] *(similar)* — Deploy and configure Wazuh SIEM/XDR for endpoint detection including agent management, custom decoder and rule XML creation, alert querying via the Wazuh REST API, and automated response actions.
- [[implementing-siem-use-case-tuning]] *(similar)* — Tune SIEM detection rules to reduce false positives by analyzing alert volumes, creating whitelists, adjusting thresholds, and measuring detection efficacy metrics in Splunk and Elastic
- [[investigating-insider-threat-indicators]] *(similar)* — Investigates insider threat indicators including data exfiltration attempts, unauthorized access patterns, policy violations, and pre-departure behaviors using SIEM analytics, DLP alerts, and HR data correlation. Use when SOC teams receive insider threat referrals from HR, detect anomalous data move
- [[mapping-mitre-attack-techniques]] *(similar)* — Maps observed adversary behaviors, security alerts, and detection rules to MITRE ATT&CK techniques and sub-techniques to quantify detection coverage and guide control prioritization. Use when building an ATT&CK-based coverage heatmap, tagging SIEM alerts with technique IDs, aligning security control
- [[performing-cloud-native-forensics-with-falco]] *(similar)* — Uses Falco YAML rules for runtime threat detection in containers and Kubernetes, monitoring syscalls for shell spawns, file tampering, network anomalies, and privilege escalation. Manages Falco rules via the Falco gRPC API and parses Falco alert output. Use when building container runtime security o
- [[performing-cloud-native-threat-hunting-with-aws-detective]] *(similar)* — Hunt for threats in AWS environments using Detective behavior graphs, entity investigation timelines, GuardDuty finding correlation, and automated entity profiling across IAM users, EC2 instances, and IP addresses.
- [[performing-false-positive-reduction-in-siem]] *(similar)* — Perform systematic SIEM false positive reduction through rule tuning, threshold adjustment, correlation refinement, and threat intelligence enrichment to combat alert fatigue.
- [[performing-log-source-onboarding-in-siem]] *(similar)* — Perform structured log source onboarding into SIEM platforms by configuring collectors, parsers, normalization, and validation for complete security visibility.
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
- [[analyzing-bootkit-and-rootkit-samples]] — Anthropic-Cybersecurity-Skills
- [[analyzing-campaign-attribution-evidence]] — Anthropic-Cybersecurity-Skills
