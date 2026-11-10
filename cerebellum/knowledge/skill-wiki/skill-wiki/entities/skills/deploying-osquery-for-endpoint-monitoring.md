---
title: deploying-osquery-for-endpoint-monitoring
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [configuring-host-based-intrusion-detection, configuring-suricata-for-network-monitoring, configuring-windows-event-logging-for-detection, deploying-edr-agent-with-crowdstrike, deploying-ransomware-canary-files, detecting-network-anomalies-with-zeek, implementing-endpoint-detection-with-wazuh, implementing-security-monitoring-with-datadog, performing-cloud-native-forensics-with-falco]
confidence: low
---

Deploys and configures osquery for real-time endpoint monitoring using SQL-based queries to inspect running processes, open ports, installed software, and system configuration. Use when building visibility into endpoint state, threat hunting across fleet, or implementing compliance monitoring. Activ

## Metadata

- **ID:** `deploying-osquery-for-endpoint-monitoring`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/deploying-osquery-for-endpoint-monitoring/SKILL.md`
- **Score:** 38.0
- **Edges:** 9

## Related Skills

- [[configuring-windows-event-logging-for-detection]] *(similar)* — Configures Windows Event Logging with advanced audit policies to generate high-fidelity security events for threat detection and forensic investigation. Use when enabling audit policies for logon events, process creation, privilege use, and object access to feed SIEM detection rules. Activates for r
- [[detecting-network-anomalies-with-zeek]] *(similar)* — Deploys and configures Zeek (formerly Bro) network security monitor to passively analyze network traffic, generate structured logs, detect anomalous behavior, and create custom detection scripts for threat hunting and incident response.

- [[implementing-endpoint-detection-with-wazuh]] *(similar)* — Deploy and configure Wazuh SIEM/XDR for endpoint detection including agent management, custom decoder and rule XML creation, alert querying via the Wazuh REST API, and automated response actions.
- [[implementing-security-monitoring-with-datadog]] *(similar)* — Implements security monitoring using Datadog Cloud SIEM, Cloud Security Management (CSM), and Workload Protection to detect threats, enforce compliance, and respond to security events across cloud and hybrid infrastructure. Covers Agent deployment, log source ingestion, detection rule creation, secu
- [[performing-cloud-native-forensics-with-falco]] *(similar)* — Uses Falco YAML rules for runtime threat detection in containers and Kubernetes, monitoring syscalls for shell spawns, file tampering, network anomalies, and privilege escalation. Manages Falco rules via the Falco gRPC API and parses Falco alert output. Use when building container runtime security o
- [[configuring-host-based-intrusion-detection]] *(similar)* — Configures host-based intrusion detection systems (HIDS) to monitor endpoint file integrity, system calls, and configuration changes for security violations. Use when deploying OSSEC, Wazuh, or AIDE for endpoint monitoring, building file integrity monitoring (FIM) policies, or meeting compliance req
- [[configuring-suricata-for-network-monitoring]] *(similar)* — Deploys and configures Suricata IDS/IPS with Emerging Threats rulesets, EVE JSON logging, and custom rules for real-time network traffic inspection, threat detection, and integration with SIEM platforms for centralized security monitoring.

- [[deploying-edr-agent-with-crowdstrike]] *(similar)* — Deploys and configures CrowdStrike Falcon EDR agents across enterprise endpoints to enable real-time threat detection, behavioral analysis, and automated response. Use when onboarding endpoints to EDR coverage, configuring detection policies, or integrating Falcon telemetry with SIEM platforms. Acti
- [[deploying-ransomware-canary-files]] *(similar)* — Deploys and monitors ransomware canary files across critical directories using Python's watchdog library for real-time filesystem event detection. Places strategically named decoy files that mimic high-value targets (financial records, credentials, database exports) in locations ransomware typically

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
