---
title: implementing-endpoint-detection-with-wazuh
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [building-cloud-siem-with-sentinel, configuring-host-based-intrusion-detection, configuring-suricata-for-network-monitoring, deploying-edr-agent-with-crowdstrike, deploying-osquery-for-endpoint-monitoring, implementing-dragos-platform-for-ot-monitoring, implementing-file-integrity-monitoring-with-aide, implementing-log-forwarding-with-fluentd, implementing-security-monitoring-with-datadog, implementing-semgrep-for-custom-sast-rules, implementing-siem-use-case-tuning, implementing-siem-use-cases-for-detection, implementing-web-application-logging-with-modsecurity, operationalizing-misp-threat-feeds, performing-false-positive-reduction-in-siem, performing-threat-hunting-with-elastic-siem, securing-api-gateway-with-aws-waf]
confidence: low
---

Deploy and configure Wazuh SIEM/XDR for endpoint detection including agent management, custom decoder and rule XML creation, alert querying via the Wazuh REST API, and automated response actions.

## Metadata

- **ID:** `implementing-endpoint-detection-with-wazuh`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/implementing-endpoint-detection-with-wazuh/SKILL.md`
- **Score:** 21.0
- **Edges:** 17

## Related Skills

- [[building-cloud-siem-with-sentinel]] *(similar)* — This skill covers deploying Microsoft Sentinel as a cloud-native SIEM and SOAR platform for centralized security operations. It details configuring data connectors for multi-cloud log ingestion, writing KQL detection queries, building automated response playbooks with Logic Apps, and leveraging the 
- [[implementing-security-monitoring-with-datadog]] *(similar)* — Implements security monitoring using Datadog Cloud SIEM, Cloud Security Management (CSM), and Workload Protection to detect threats, enforce compliance, and respond to security events across cloud and hybrid infrastructure. Covers Agent deployment, log source ingestion, detection rule creation, secu
- [[implementing-siem-use-case-tuning]] *(similar)* — Tune SIEM detection rules to reduce false positives by analyzing alert volumes, creating whitelists, adjusting thresholds, and measuring detection efficacy metrics in Splunk and Elastic
- [[implementing-siem-use-cases-for-detection]] *(similar)* — Implements SIEM detection use cases by designing correlation rules, threshold alerts, and behavioral analytics mapped to MITRE ATT&CK techniques across Splunk, Elastic, and Sentinel. Use when SOC teams need to expand detection coverage, formalize use case lifecycle management, or build a detection l
- [[performing-threat-hunting-with-elastic-siem]] *(similar)* — Performs proactive threat hunting in Elastic Security SIEM using KQL/EQL queries, detection rules, and Timeline investigation to identify threats that evade automated detection. Use when SOC teams need to hunt for specific ATT&CK techniques, investigate anomalous behaviors, or validate detection cov
- [[configuring-host-based-intrusion-detection]] *(similar)* — Configures host-based intrusion detection systems (HIDS) to monitor endpoint file integrity, system calls, and configuration changes for security violations. Use when deploying OSSEC, Wazuh, or AIDE for endpoint monitoring, building file integrity monitoring (FIM) policies, or meeting compliance req
- [[configuring-suricata-for-network-monitoring]] *(similar)* — Deploys and configures Suricata IDS/IPS with Emerging Threats rulesets, EVE JSON logging, and custom rules for real-time network traffic inspection, threat detection, and integration with SIEM platforms for centralized security monitoring.

- [[deploying-edr-agent-with-crowdstrike]] *(similar)* — Deploys and configures CrowdStrike Falcon EDR agents across enterprise endpoints to enable real-time threat detection, behavioral analysis, and automated response. Use when onboarding endpoints to EDR coverage, configuring detection policies, or integrating Falcon telemetry with SIEM platforms. Acti
- [[deploying-osquery-for-endpoint-monitoring]] *(similar)* — Deploys and configures osquery for real-time endpoint monitoring using SQL-based queries to inspect running processes, open ports, installed software, and system configuration. Use when building visibility into endpoint state, threat hunting across fleet, or implementing compliance monitoring. Activ
- [[implementing-dragos-platform-for-ot-monitoring]] *(similar)* — Deploy and configure the Dragos Platform for OT network monitoring, leveraging its 600+ industrial protocol parsers, intelligence-driven threat detection analytics, and asset visibility capabilities to protect ICS environments against threat groups like VOLTZITE, GRAPHITE, and BAUXITE.

- [[implementing-file-integrity-monitoring-with-aide]] *(similar)* — Configure AIDE (Advanced Intrusion Detection Environment) for file integrity monitoring including baseline creation, scheduled integrity checks, change detection, and alerting
- [[implementing-log-forwarding-with-fluentd]] *(similar)* — Configure Fluentd and Fluent Bit for centralized log aggregation, routing, filtering, and enrichment across distributed infrastructure
- [[implementing-semgrep-for-custom-sast-rules]] *(similar)* — Write custom Semgrep SAST rules in YAML to detect application-specific vulnerabilities, enforce coding standards, and integrate into CI/CD pipelines.
- [[implementing-web-application-logging-with-modsecurity]] *(similar)* — Configure ModSecurity WAF with OWASP Core Rule Set (CRS) for web application logging, tune rules to reduce false positives, analyze audit logs for attack detection, and implement custom SecRules for application-specific threats. The analyst configures SecRuleEngine, SecAuditEngine, and CRS paranoia 
- [[operationalizing-misp-threat-feeds]] *(similar)* — Run MISP, curate feeds, and auto-generate detections for Wazuh, Sigma, and Suricata.
- [[performing-false-positive-reduction-in-siem]] *(similar)* — Perform systematic SIEM false positive reduction through rule tuning, threshold adjustment, correlation refinement, and threat intelligence enrichment to combat alert fatigue.
- [[securing-api-gateway-with-aws-waf]] *(similar)* — Securing API Gateway endpoints with AWS WAF by configuring managed rule groups for OWASP Top 10 protection, creating custom rate limiting rules, implementing bot control, setting up IP reputation filtering, and monitoring WAF metrics for security effectiveness.


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
