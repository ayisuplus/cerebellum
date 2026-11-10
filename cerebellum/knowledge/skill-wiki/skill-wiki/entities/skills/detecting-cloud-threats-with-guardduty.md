---
title: detecting-cloud-threats-with-guardduty
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [building-cloud-siem-with-sentinel, detecting-aws-cloudtrail-anomalies, detecting-aws-guardduty-findings-automation, detecting-cryptomining-in-cloud, detecting-s3-data-exfiltration-attempts, implementing-aws-security-hub, implementing-cloud-security-posture-management, implementing-cloud-trail-log-analysis, implementing-cloud-workload-protection, implementing-security-monitoring-with-datadog, performing-cloud-native-threat-hunting-with-aws-detective, securing-kubernetes-on-cloud]
confidence: medium
---

This skill teaches security teams how to deploy and operationalize Amazon GuardDuty for continuous threat detection across AWS accounts and workloads. It covers enabling protection plans for S3, EKS, EC2 runtime monitoring, and Lambda, interpreting finding severity levels, and building automated res

## Metadata

- **ID:** `detecting-cloud-threats-with-guardduty`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-cloud-threats-with-guardduty/SKILL.md`
- **Score:** 52.0
- **Edges:** 12

## Related Skills

- [[detecting-cryptomining-in-cloud]] *(complement)* — This skill teaches security teams how to detect and respond to unauthorized cryptocurrency mining operations in cloud environments. It covers identifying cryptomining indicators through compute usage anomalies, network traffic patterns to mining pools, GuardDuty CryptoCurrency findings, and runtime 
- [[performing-cloud-native-threat-hunting-with-aws-detective]] *(complement)* — Hunt for threats in AWS environments using Detective behavior graphs, entity investigation timelines, GuardDuty finding correlation, and automated entity profiling across IAM users, EC2 instances, and IP addresses.
- [[detecting-aws-cloudtrail-anomalies]] *(similar)* — Detect unusual API call patterns in AWS CloudTrail logs using boto3, statistical baselining, and behavioral analysis to identify credential compromise, privilege escalation, and unauthorized resource access.
- [[detecting-s3-data-exfiltration-attempts]] *(similar)* — Detecting data exfiltration attempts from AWS S3 buckets by analyzing CloudTrail S3 data events, VPC Flow Logs, GuardDuty findings, Amazon Macie alerts, and S3 access patterns to identify unauthorized bulk downloads and cross-account data transfers.

- [[implementing-security-monitoring-with-datadog]] *(similar)* — Implements security monitoring using Datadog Cloud SIEM, Cloud Security Management (CSM), and Workload Protection to detect threats, enforce compliance, and respond to security events across cloud and hybrid infrastructure. Covers Agent deployment, log source ingestion, detection rule creation, secu
- [[detecting-aws-guardduty-findings-automation]] *(bridge)* — Automate AWS GuardDuty threat detection findings processing using EventBridge and Lambda to enable real-time incident response, automatic quarantine of compromised resources, and security notification workflows.
- [[implementing-aws-security-hub]] *(bridge)* — This skill covers deploying AWS Security Hub as a centralized cloud security posture management platform that aggregates findings from GuardDuty, Inspector, Macie, and third-party tools. It details enabling security standards like CIS AWS Foundations Benchmark, configuring automated remediation, and
- [[building-cloud-siem-with-sentinel]] *(similar)* — This skill covers deploying Microsoft Sentinel as a cloud-native SIEM and SOAR platform for centralized security operations. It details configuring data connectors for multi-cloud log ingestion, writing KQL detection queries, building automated response playbooks with Logic Apps, and leveraging the 
- [[implementing-cloud-security-posture-management]] *(similar)* — Implementing Cloud Security Posture Management (CSPM) to continuously monitor multi-cloud environments for misconfigurations, compliance violations, and security risks using Prowler, ScoutSuite, AWS Security Hub, Azure Defender, and GCP Security Command Center.

- [[implementing-cloud-trail-log-analysis]] *(similar)* — Implementing AWS CloudTrail log analysis for security monitoring, threat detection, and forensic investigation using Athena, CloudWatch Logs Insights, and SIEM integration to identify unauthorized access, privilege escalation, and suspicious API activity.

- [[implementing-cloud-workload-protection]] *(similar)* — Implements cloud workload protection using boto3 and google-cloud APIs for runtime security monitoring, process anomaly detection, and file integrity checking on EC2/GCE instances. Scans for cryptomining, reverse shells, and unauthorized binaries. Use when building runtime security controls for clou
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
