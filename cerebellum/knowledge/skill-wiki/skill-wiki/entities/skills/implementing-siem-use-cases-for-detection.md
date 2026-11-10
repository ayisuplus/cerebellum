---
title: implementing-siem-use-cases-for-detection
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [building-attack-pattern-library-from-cti-reports, building-cloud-siem-with-sentinel, building-detection-rule-with-splunk-spl, building-detection-rules-with-sigma, building-soc-metrics-and-kpi-tracking, correlating-security-events-in-qradar, deploying-edr-agent-with-crowdstrike, implementing-alert-fatigue-reduction, implementing-endpoint-detection-with-wazuh, implementing-security-monitoring-with-datadog, implementing-siem-correlation-rules-for-apt, implementing-siem-use-case-tuning, implementing-ticketing-system-for-incidents, implementing-vulnerability-sla-breach-alerting, investigating-insider-threat-indicators, mapping-mitre-attack-techniques, operationalizing-misp-threat-feeds, performing-alert-triage-with-elastic-siem, performing-false-positive-reduction-in-siem, performing-log-source-onboarding-in-siem, performing-purple-team-atomic-testing, performing-threat-hunting-with-elastic-siem, performing-user-behavior-analytics, triaging-security-alerts-in-splunk]
confidence: medium
---

Implements SIEM detection use cases by designing correlation rules, threshold alerts, and behavioral analytics mapped to MITRE ATT&CK techniques across Splunk, Elastic, and Sentinel. Use when SOC teams need to expand detection coverage, formalize use case lifecycle management, or build a detection l

## Metadata

- **ID:** `implementing-siem-use-cases-for-detection`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/implementing-siem-use-cases-for-detection/SKILL.md`
- **Score:** 52.0
- **Edges:** 24

## Related Skills

- [[mapping-mitre-attack-techniques]] *(complement)* — Maps observed adversary behaviors, security alerts, and detection rules to MITRE ATT&CK techniques and sub-techniques to quantify detection coverage and guide control prioritization. Use when building an ATT&CK-based coverage heatmap, tagging SIEM alerts with technique IDs, aligning security control
- [[performing-threat-hunting-with-elastic-siem]] *(complement)* — Performs proactive threat hunting in Elastic Security SIEM using KQL/EQL queries, detection rules, and Timeline investigation to identify threats that evade automated detection. Use when SOC teams need to hunt for specific ATT&CK techniques, investigate anomalous behaviors, or validate detection cov
- [[implementing-ticketing-system-for-incidents]] *(similar)* — Implements an integrated incident ticketing system connecting SIEM alerts to ServiceNow, Jira, or TheHive for structured incident tracking, SLA management, escalation workflows, and compliance documentation. Use when SOC teams need formalized incident lifecycle management with automated ticket creat
- [[performing-alert-triage-with-elastic-siem]] *(similar)* — Perform systematic alert triage in Elastic Security SIEM to rapidly classify, prioritize, and investigate security alerts for SOC operations.
- [[performing-false-positive-reduction-in-siem]] *(similar)* — Perform systematic SIEM false positive reduction through rule tuning, threshold adjustment, correlation refinement, and threat intelligence enrichment to combat alert fatigue.
- [[building-detection-rule-with-splunk-spl]] *(complement)* — Build effective detection rules using Splunk Search Processing Language (SPL) correlation searches to identify security threats in SOC environments.
- [[building-detection-rules-with-sigma]] *(complement)* — Builds vendor-agnostic detection rules using the Sigma rule format for threat detection across SIEM platforms including Splunk, Elastic, and Microsoft Sentinel. Use when creating portable detection logic from threat intelligence, mapping rules to MITRE ATT&CK techniques, or converting community Sigm
- [[implementing-siem-use-case-tuning]] *(complement)* — Tune SIEM detection rules to reduce false positives by analyzing alert volumes, creating whitelists, adjusting thresholds, and measuring detection efficacy metrics in Splunk and Elastic
- [[building-attack-pattern-library-from-cti-reports]] *(similar)* — Extract and catalog attack patterns from cyber threat intelligence reports into a structured STIX-based library mapped to MITRE ATT&CK for detection engineering and threat-informed defense.
- [[building-cloud-siem-with-sentinel]] *(similar)* — This skill covers deploying Microsoft Sentinel as a cloud-native SIEM and SOAR platform for centralized security operations. It details configuring data connectors for multi-cloud log ingestion, writing KQL detection queries, building automated response playbooks with Logic Apps, and leveraging the 
- [[building-soc-metrics-and-kpi-tracking]] *(similar)* — Builds SOC performance metrics and KPI tracking dashboards measuring Mean Time to Detect (MTTD), Mean Time to Respond (MTTR), alert quality ratios, analyst productivity, and detection coverage using SIEM data. Use when SOC leadership needs operational visibility, continuous improvement tracking, or 
- [[correlating-security-events-in-qradar]] *(similar)* — Correlates security events in IBM QRadar SIEM using AQL (Ariel Query Language), custom rules, building blocks, and offense management to detect multi-stage attacks across network, endpoint, and application log sources. Use when SOC analysts need to investigate QRadar offenses, build correlation rule
- [[deploying-edr-agent-with-crowdstrike]] *(similar)* — Deploys and configures CrowdStrike Falcon EDR agents across enterprise endpoints to enable real-time threat detection, behavioral analysis, and automated response. Use when onboarding endpoints to EDR coverage, configuring detection policies, or integrating Falcon telemetry with SIEM platforms. Acti
- [[implementing-alert-fatigue-reduction]] *(similar)* — Implements strategies to reduce SOC alert fatigue by tuning detection rules, consolidating duplicate alerts, implementing risk-based alerting, and measuring alert quality metrics to maintain analyst effectiveness and prevent critical alert dismissal. Use when SOC teams face overwhelming alert volume
- [[implementing-endpoint-detection-with-wazuh]] *(similar)* — Deploy and configure Wazuh SIEM/XDR for endpoint detection including agent management, custom decoder and rule XML creation, alert querying via the Wazuh REST API, and automated response actions.
- [[implementing-security-monitoring-with-datadog]] *(similar)* — Implements security monitoring using Datadog Cloud SIEM, Cloud Security Management (CSM), and Workload Protection to detect threats, enforce compliance, and respond to security events across cloud and hybrid infrastructure. Covers Agent deployment, log source ingestion, detection rule creation, secu
- [[implementing-siem-correlation-rules-for-apt]] *(similar)* — Write multi-event correlation rules that detect APT lateral movement by chaining Windows authentication events, process execution telemetry, and network connection logs across hosts. Uses Splunk SPL and Sigma rule format to correlate Event IDs 4624, 4648, 4688, and Sysmon Events 1/3 within sliding t
- [[implementing-vulnerability-sla-breach-alerting]] *(similar)* — Build automated alerting for vulnerability remediation SLA breaches with severity-based timelines, escalation workflows, and compliance reporting dashboards.
- [[investigating-insider-threat-indicators]] *(similar)* — Investigates insider threat indicators including data exfiltration attempts, unauthorized access patterns, policy violations, and pre-departure behaviors using SIEM analytics, DLP alerts, and HR data correlation. Use when SOC teams receive insider threat referrals from HR, detect anomalous data move
- [[operationalizing-misp-threat-feeds]] *(similar)* — Run MISP, curate feeds, and auto-generate detections for Wazuh, Sigma, and Suricata.
- [[performing-log-source-onboarding-in-siem]] *(similar)* — Perform structured log source onboarding into SIEM platforms by configuring collectors, parsers, normalization, and validation for complete security visibility.
- [[performing-purple-team-atomic-testing]] *(similar)* — Executes Atomic Red Team tests mapped to MITRE ATT&CK techniques, performs coverage gap analysis across the ATT&CK matrix, and runs detection validation loops to measure blue team visibility. Covers Invoke-AtomicRedTeam PowerShell execution, ATT&CK Navigator layer generation for heatmaps, Sigma rule
- [[performing-user-behavior-analytics]] *(similar)* — Performs User and Entity Behavior Analytics (UEBA) to detect anomalous user activities including impossible travel, unusual access patterns, privilege abuse, and insider threats using SIEM-based behavioral baselines and statistical analysis. Use when SOC teams need to identify compromised accounts o
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
