---
title: building-detection-rules-with-sigma
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [building-attack-pattern-library-from-cti-reports, building-cloud-siem-with-sentinel, building-detection-rule-with-splunk-spl, building-soc-metrics-and-kpi-tracking, hunting-evtx-with-chainsaw, implementing-siem-correlation-rules-for-apt, implementing-siem-use-case-tuning, implementing-siem-use-cases-for-detection, mapping-mitre-attack-techniques, operationalizing-misp-threat-feeds, performing-cloud-native-forensics-with-falco, performing-purple-team-atomic-testing, performing-threat-hunting-with-elastic-siem]
confidence: low
---

Builds vendor-agnostic detection rules using the Sigma rule format for threat detection across SIEM platforms including Splunk, Elastic, and Microsoft Sentinel. Use when creating portable detection logic from threat intelligence, mapping rules to MITRE ATT&CK techniques, or converting community Sigm

## Metadata

- **ID:** `building-detection-rules-with-sigma`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/building-detection-rules-with-sigma/SKILL.md`
- **Score:** 36.0
- **Edges:** 13

## Related Skills

- [[implementing-siem-use-cases-for-detection]] *(complement)* — Implements SIEM detection use cases by designing correlation rules, threshold alerts, and behavioral analytics mapped to MITRE ATT&CK techniques across Splunk, Elastic, and Sentinel. Use when SOC teams need to expand detection coverage, formalize use case lifecycle management, or build a detection l
- [[implementing-siem-correlation-rules-for-apt]] *(similar)* — Write multi-event correlation rules that detect APT lateral movement by chaining Windows authentication events, process execution telemetry, and network connection logs across hosts. Uses Splunk SPL and Sigma rule format to correlate Event IDs 4624, 4648, 4688, and Sysmon Events 1/3 within sliding t
- [[implementing-siem-use-case-tuning]] *(similar)* — Tune SIEM detection rules to reduce false positives by analyzing alert volumes, creating whitelists, adjusting thresholds, and measuring detection efficacy metrics in Splunk and Elastic
- [[mapping-mitre-attack-techniques]] *(similar)* — Maps observed adversary behaviors, security alerts, and detection rules to MITRE ATT&CK techniques and sub-techniques to quantify detection coverage and guide control prioritization. Use when building an ATT&CK-based coverage heatmap, tagging SIEM alerts with technique IDs, aligning security control
- [[performing-threat-hunting-with-elastic-siem]] *(similar)* — Performs proactive threat hunting in Elastic Security SIEM using KQL/EQL queries, detection rules, and Timeline investigation to identify threats that evade automated detection. Use when SOC teams need to hunt for specific ATT&CK techniques, investigate anomalous behaviors, or validate detection cov
- [[building-detection-rule-with-splunk-spl]] *(complement)* — Build effective detection rules using Splunk Search Processing Language (SPL) correlation searches to identify security threats in SOC environments.
- [[building-attack-pattern-library-from-cti-reports]] *(similar)* — Extract and catalog attack patterns from cyber threat intelligence reports into a structured STIX-based library mapped to MITRE ATT&CK for detection engineering and threat-informed defense.
- [[building-cloud-siem-with-sentinel]] *(similar)* — This skill covers deploying Microsoft Sentinel as a cloud-native SIEM and SOAR platform for centralized security operations. It details configuring data connectors for multi-cloud log ingestion, writing KQL detection queries, building automated response playbooks with Logic Apps, and leveraging the 
- [[building-soc-metrics-and-kpi-tracking]] *(similar)* — Builds SOC performance metrics and KPI tracking dashboards measuring Mean Time to Detect (MTTD), Mean Time to Respond (MTTR), alert quality ratios, analyst productivity, and detection coverage using SIEM data. Use when SOC leadership needs operational visibility, continuous improvement tracking, or 
- [[hunting-evtx-with-chainsaw]] *(similar)* — Perform rapid Sigma and keyword hunting across Windows event logs with Chainsaw.
- [[operationalizing-misp-threat-feeds]] *(similar)* — Run MISP, curate feeds, and auto-generate detections for Wazuh, Sigma, and Suricata.
- [[performing-cloud-native-forensics-with-falco]] *(similar)* — Uses Falco YAML rules for runtime threat detection in containers and Kubernetes, monitoring syscalls for shell spawns, file tampering, network anomalies, and privilege escalation. Manages Falco rules via the Falco gRPC API and parses Falco alert output. Use when building container runtime security o
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
