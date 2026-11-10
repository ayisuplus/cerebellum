---
title: performing-cloud-native-forensics-with-falco
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-kubernetes-audit-logs, analyzing-linux-audit-logs-for-intrusion, building-detection-rules-with-sigma, configuring-suricata-for-network-monitoring, deploying-osquery-for-endpoint-monitoring, detecting-container-drift-at-runtime, detecting-container-escape-attempts, detecting-privilege-escalation-in-kubernetes-pods, implementing-cloud-workload-protection, implementing-security-monitoring-with-datadog, performing-cloud-native-threat-hunting-with-aws-detective, performing-threat-hunting-with-elastic-siem]
confidence: low
---

Uses Falco YAML rules for runtime threat detection in containers and Kubernetes, monitoring syscalls for shell spawns, file tampering, network anomalies, and privilege escalation. Manages Falco rules via the Falco gRPC API and parses Falco alert output. Use when building container runtime security o

## Metadata

- **ID:** `performing-cloud-native-forensics-with-falco`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/performing-cloud-native-forensics-with-falco/SKILL.md`
- **Score:** 36.0
- **Edges:** 12

## Related Skills

- [[analyzing-linux-audit-logs-for-intrusion]] *(similar)* — Uses the Linux Audit framework (auditd) with ausearch and aureport utilities to detect intrusion attempts, unauthorized access, privilege escalation, and suspicious system activity. Covers audit rule configuration, log querying, timeline reconstruction, and integration with SIEM platforms. Activates
- [[building-detection-rules-with-sigma]] *(similar)* — Builds vendor-agnostic detection rules using the Sigma rule format for threat detection across SIEM platforms including Splunk, Elastic, and Microsoft Sentinel. Use when creating portable detection logic from threat intelligence, mapping rules to MITRE ATT&CK techniques, or converting community Sigm
- [[configuring-suricata-for-network-monitoring]] *(similar)* — Deploys and configures Suricata IDS/IPS with Emerging Threats rulesets, EVE JSON logging, and custom rules for real-time network traffic inspection, threat detection, and integration with SIEM platforms for centralized security monitoring.

- [[performing-cloud-native-threat-hunting-with-aws-detective]] *(similar)* — Hunt for threats in AWS environments using Detective behavior graphs, entity investigation timelines, GuardDuty finding correlation, and automated entity profiling across IAM users, EC2 instances, and IP addresses.
- [[performing-threat-hunting-with-elastic-siem]] *(similar)* — Performs proactive threat hunting in Elastic Security SIEM using KQL/EQL queries, detection rules, and Timeline investigation to identify threats that evade automated detection. Use when SOC teams need to hunt for specific ATT&CK techniques, investigate anomalous behaviors, or validate detection cov
- [[detecting-privilege-escalation-in-kubernetes-pods]] *(complement)* — Detect and prevent privilege escalation in Kubernetes pods by monitoring security contexts, capabilities, and syscall patterns with Falco and OPA policies.
- [[analyzing-kubernetes-audit-logs]] *(similar)* — Parses Kubernetes API server audit logs (JSON lines) to detect exec-into-pod, secret access, RBAC modifications, privileged pod creation, and anonymous API access. Builds threat detection rules from audit event patterns. Use when investigating Kubernetes cluster compromise or building k8s-specific S
- [[deploying-osquery-for-endpoint-monitoring]] *(similar)* — Deploys and configures osquery for real-time endpoint monitoring using SQL-based queries to inspect running processes, open ports, installed software, and system configuration. Use when building visibility into endpoint state, threat hunting across fleet, or implementing compliance monitoring. Activ
- [[detecting-container-drift-at-runtime]] *(similar)* — Detect unauthorized modifications to running containers by monitoring for binary execution drift, file system changes, and configuration deviations from the original container image.
- [[detecting-container-escape-attempts]] *(similar)* — Container escape is a critical attack technique where an adversary breaks out of container isolation to access the host system or other containers. Detection involves monitoring for escape indicators
- [[implementing-cloud-workload-protection]] *(similar)* — Implements cloud workload protection using boto3 and google-cloud APIs for runtime security monitoring, process anomaly detection, and file integrity checking on EC2/GCE instances. Scans for cryptomining, reverse shells, and unauthorized binaries. Use when building runtime security controls for clou
- [[implementing-security-monitoring-with-datadog]] *(similar)* — Implements security monitoring using Datadog Cloud SIEM, Cloud Security Management (CSM), and Workload Protection to detect threats, enforce compliance, and respond to security events across cloud and hybrid infrastructure. Covers Agent deployment, log source ingestion, detection rule creation, secu

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
