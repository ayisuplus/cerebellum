---
title: implementing-security-monitoring-with-datadog
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [building-cloud-siem-with-sentinel, deploying-edr-agent-with-crowdstrike, deploying-osquery-for-endpoint-monitoring, detecting-cloud-threats-with-guardduty, detecting-privilege-escalation-in-kubernetes-pods, implementing-cloud-security-posture-management, implementing-cloud-trail-log-analysis, implementing-cloud-workload-protection, implementing-dragos-platform-for-ot-monitoring, implementing-endpoint-detection-with-wazuh, implementing-endpoint-dlp-controls, implementing-gcp-vpc-firewall-rules, implementing-log-forwarding-with-fluentd, implementing-privileged-access-management-with-cyberark, implementing-privileged-session-monitoring, implementing-secret-scanning-with-gitleaks, implementing-secrets-scanning-in-ci-cd, implementing-security-chaos-engineering, implementing-semgrep-for-custom-sast-rules, implementing-siem-use-case-tuning, implementing-siem-use-cases-for-detection, implementing-ticketing-system-for-incidents, implementing-vulnerability-sla-breach-alerting, implementing-web-application-logging-with-modsecurity, performing-cloud-native-forensics-with-falco, performing-cloud-native-threat-hunting-with-aws-detective, performing-log-source-onboarding-in-siem, securing-api-gateway-with-aws-waf, securing-kubernetes-on-cloud]
confidence: medium
---

Implements security monitoring using Datadog Cloud SIEM, Cloud Security Management (CSM), and Workload Protection to detect threats, enforce compliance, and respond to security events across cloud and hybrid infrastructure. Covers Agent deployment, log source ingestion, detection rule creation, secu

## Metadata

- **ID:** `implementing-security-monitoring-with-datadog`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/implementing-security-monitoring-with-datadog/SKILL.md`
- **Score:** 45.0
- **Edges:** 29

## Related Skills

- [[implementing-semgrep-for-custom-sast-rules]] *(similar)* — Write custom Semgrep SAST rules in YAML to detect application-specific vulnerabilities, enforce coding standards, and integrate into CI/CD pipelines.
- [[implementing-siem-use-case-tuning]] *(similar)* — Tune SIEM detection rules to reduce false positives by analyzing alert volumes, creating whitelists, adjusting thresholds, and measuring detection efficacy metrics in Splunk and Elastic
- [[implementing-siem-use-cases-for-detection]] *(similar)* — Implements SIEM detection use cases by designing correlation rules, threshold alerts, and behavioral analytics mapped to MITRE ATT&CK techniques across Splunk, Elastic, and Sentinel. Use when SOC teams need to expand detection coverage, formalize use case lifecycle management, or build a detection l
- [[implementing-vulnerability-sla-breach-alerting]] *(similar)* — Build automated alerting for vulnerability remediation SLA breaches with severity-based timelines, escalation workflows, and compliance reporting dashboards.
- [[performing-cloud-native-forensics-with-falco]] *(similar)* — Uses Falco YAML rules for runtime threat detection in containers and Kubernetes, monitoring syscalls for shell spawns, file tampering, network anomalies, and privilege escalation. Manages Falco rules via the Falco gRPC API and parses Falco alert output. Use when building container runtime security o
- [[implementing-cloud-trail-log-analysis]] *(complement)* — Implementing AWS CloudTrail log analysis for security monitoring, threat detection, and forensic investigation using Athena, CloudWatch Logs Insights, and SIEM integration to identify unauthorized access, privilege escalation, and suspicious API activity.

- [[building-cloud-siem-with-sentinel]] *(similar)* — This skill covers deploying Microsoft Sentinel as a cloud-native SIEM and SOAR platform for centralized security operations. It details configuring data connectors for multi-cloud log ingestion, writing KQL detection queries, building automated response playbooks with Logic Apps, and leveraging the 
- [[deploying-edr-agent-with-crowdstrike]] *(similar)* — Deploys and configures CrowdStrike Falcon EDR agents across enterprise endpoints to enable real-time threat detection, behavioral analysis, and automated response. Use when onboarding endpoints to EDR coverage, configuring detection policies, or integrating Falcon telemetry with SIEM platforms. Acti
- [[deploying-osquery-for-endpoint-monitoring]] *(similar)* — Deploys and configures osquery for real-time endpoint monitoring using SQL-based queries to inspect running processes, open ports, installed software, and system configuration. Use when building visibility into endpoint state, threat hunting across fleet, or implementing compliance monitoring. Activ
- [[detecting-cloud-threats-with-guardduty]] *(similar)* — This skill teaches security teams how to deploy and operationalize Amazon GuardDuty for continuous threat detection across AWS accounts and workloads. It covers enabling protection plans for S3, EKS, EC2 runtime monitoring, and Lambda, interpreting finding severity levels, and building automated res
- [[detecting-privilege-escalation-in-kubernetes-pods]] *(similar)* — Detect and prevent privilege escalation in Kubernetes pods by monitoring security contexts, capabilities, and syscall patterns with Falco and OPA policies.
- [[implementing-cloud-security-posture-management]] *(similar)* — Implementing Cloud Security Posture Management (CSPM) to continuously monitor multi-cloud environments for misconfigurations, compliance violations, and security risks using Prowler, ScoutSuite, AWS Security Hub, Azure Defender, and GCP Security Command Center.

- [[implementing-cloud-workload-protection]] *(similar)* — Implements cloud workload protection using boto3 and google-cloud APIs for runtime security monitoring, process anomaly detection, and file integrity checking on EC2/GCE instances. Scans for cryptomining, reverse shells, and unauthorized binaries. Use when building runtime security controls for clou
- [[implementing-dragos-platform-for-ot-monitoring]] *(similar)* — Deploy and configure the Dragos Platform for OT network monitoring, leveraging its 600+ industrial protocol parsers, intelligence-driven threat detection analytics, and asset visibility capabilities to protect ICS environments against threat groups like VOLTZITE, GRAPHITE, and BAUXITE.

- [[implementing-endpoint-detection-with-wazuh]] *(similar)* — Deploy and configure Wazuh SIEM/XDR for endpoint detection including agent management, custom decoder and rule XML creation, alert querying via the Wazuh REST API, and automated response actions.
- [[implementing-endpoint-dlp-controls]] *(similar)* — Implements endpoint Data Loss Prevention (DLP) controls to detect and prevent sensitive data exfiltration through email, USB, cloud storage, and printing. Use when deploying DLP agents, creating content inspection policies, or preventing unauthorized data movement from endpoints. Activates for reque
- [[implementing-gcp-vpc-firewall-rules]] *(similar)* — Implementing and auditing GCP VPC firewall rules to enforce network segmentation, restrict ingress and egress traffic, apply hierarchical firewall policies across the organization, and monitor firewall rule effectiveness using VPC Flow Logs.

- [[implementing-log-forwarding-with-fluentd]] *(similar)* — Configure Fluentd and Fluent Bit for centralized log aggregation, routing, filtering, and enrichment across distributed infrastructure
- [[implementing-privileged-access-management-with-cyberark]] *(similar)* — Deploy CyberArk Privileged Access Management to discover, vault, rotate, and monitor privileged credentials across enterprise infrastructure. This skill covers vault architecture, session isolation, c
- [[implementing-privileged-session-monitoring]] *(similar)* — Implements privileged session monitoring and recording using Privileged Access Management (PAM) solutions, focusing on CyberArk Privileged Session Manager (PSM) and open-source alternatives. Covers session recording configuration, keystroke logging, real-time monitoring, risk-based session analysis,
- [[implementing-secret-scanning-with-gitleaks]] *(similar)* — This skill covers implementing Gitleaks for detecting and preventing hardcoded secrets in git repositories. It addresses configuring pre-commit hooks, CI/CD pipeline integration, custom rule authoring for organization-specific secrets, baseline management for existing repositories, and remediation w
- [[implementing-secrets-scanning-in-ci-cd]] *(similar)* — Integrate gitleaks and trufflehog into CI/CD pipelines to detect leaked secrets before deployment
- [[implementing-security-chaos-engineering]] *(similar)* — Implements security chaos engineering experiments that deliberately disable or degrade security controls to verify detection and response capabilities. Tests WAF bypass, firewall rule removal, log pipeline disruption, and EDR disablement scenarios using boto3 and subprocess. Use when validating SOC 
- [[implementing-ticketing-system-for-incidents]] *(similar)* — Implements an integrated incident ticketing system connecting SIEM alerts to ServiceNow, Jira, or TheHive for structured incident tracking, SLA management, escalation workflows, and compliance documentation. Use when SOC teams need formalized incident lifecycle management with automated ticket creat
- [[implementing-web-application-logging-with-modsecurity]] *(similar)* — Configure ModSecurity WAF with OWASP Core Rule Set (CRS) for web application logging, tune rules to reduce false positives, analyze audit logs for attack detection, and implement custom SecRules for application-specific threats. The analyst configures SecRuleEngine, SecAuditEngine, and CRS paranoia 
- [[performing-cloud-native-threat-hunting-with-aws-detective]] *(similar)* — Hunt for threats in AWS environments using Detective behavior graphs, entity investigation timelines, GuardDuty finding correlation, and automated entity profiling across IAM users, EC2 instances, and IP addresses.
- [[performing-log-source-onboarding-in-siem]] *(similar)* — Perform structured log source onboarding into SIEM platforms by configuring collectors, parsers, normalization, and validation for complete security visibility.
- [[securing-api-gateway-with-aws-waf]] *(similar)* — Securing API Gateway endpoints with AWS WAF by configuring managed rule groups for OWASP Top 10 protection, creating custom rate limiting rules, implementing bot control, setting up IP reputation filtering, and monitoring WAF metrics for security effectiveness.

- [[securing-kubernetes-on-cloud]] *(similar)* — This skill covers hardening managed Kubernetes clusters on EKS, AKS, and GKE by implementing Pod Security Standards, network policies, workload identity, RBAC scoping, image admission controls, and runtime security monitoring. It addresses cloud-specific security features including IRSA for EKS, Wor

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
