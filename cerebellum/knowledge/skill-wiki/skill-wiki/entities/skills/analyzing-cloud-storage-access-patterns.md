---
title: analyzing-cloud-storage-access-patterns
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-kubernetes-audit-logs, detecting-aws-cloudtrail-anomalies, detecting-insider-data-exfiltration-via-dlp, detecting-misconfigured-azure-storage, detecting-s3-data-exfiltration-attempts, detecting-service-account-abuse, detecting-shadow-it-cloud-usage, implementing-cloud-trail-log-analysis, performing-cloud-log-forensics-with-athena]
confidence: low
---

Detect abnormal access patterns in AWS S3, GCS, and Azure Blob Storage by analyzing CloudTrail Data Events, GCS audit logs, and Azure Storage Analytics. Identifies after-hours bulk downloads, access from new IP addresses, unusual API calls (GetObject spikes), and potential data exfiltration using st

## Metadata

- **ID:** `analyzing-cloud-storage-access-patterns`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/analyzing-cloud-storage-access-patterns/SKILL.md`
- **Score:** 37.0
- **Edges:** 9

## Related Skills

- [[detecting-aws-cloudtrail-anomalies]] *(complement)* — Detect unusual API call patterns in AWS CloudTrail logs using boto3, statistical baselining, and behavioral analysis to identify credential compromise, privilege escalation, and unauthorized resource access.
- [[detecting-s3-data-exfiltration-attempts]] *(complement)* — Detecting data exfiltration attempts from AWS S3 buckets by analyzing CloudTrail S3 data events, VPC Flow Logs, GuardDuty findings, Amazon Macie alerts, and S3 access patterns to identify unauthorized bulk downloads and cross-account data transfers.

- [[analyzing-kubernetes-audit-logs]] *(similar)* — Parses Kubernetes API server audit logs (JSON lines) to detect exec-into-pod, secret access, RBAC modifications, privileged pod creation, and anonymous API access. Builds threat detection rules from audit event patterns. Use when investigating Kubernetes cluster compromise or building k8s-specific S
- [[detecting-insider-data-exfiltration-via-dlp]] *(similar)* — Detects insider data exfiltration by analyzing DLP policy violations, file access patterns, upload volume anomalies, and off-hours activity in endpoint and cloud logs. Uses pandas for behavioral analytics and statistical baselines. Use when investigating insider threats or building user behavior ana
- [[implementing-cloud-trail-log-analysis]] *(similar)* — Implementing AWS CloudTrail log analysis for security monitoring, threat detection, and forensic investigation using Athena, CloudWatch Logs Insights, and SIEM integration to identify unauthorized access, privilege escalation, and suspicious API activity.

- [[detecting-misconfigured-azure-storage]] *(similar)* — Detecting misconfigured Azure Storage accounts including publicly accessible blob containers, missing encryption settings, overly permissive SAS tokens, disabled logging, and network access violations using Azure CLI, PowerShell, and Microsoft Defender for Storage.

- [[detecting-service-account-abuse]] *(similar)* — Detect abuse of service accounts through anomalous interactive logons, privilege escalation, lateral movement, and unauthorized access patterns.
- [[detecting-shadow-it-cloud-usage]] *(similar)* — Detect unauthorized SaaS and cloud service usage (shadow IT) by analyzing proxy logs, DNS query logs, and netflow data using Python pandas for traffic pattern analysis and domain classification.
- [[performing-cloud-log-forensics-with-athena]] *(similar)* — Uses AWS Athena to query CloudTrail, VPC Flow Logs, S3 access logs, and ALB logs for forensic investigation. Covers CREATE TABLE DDL with partition projection, forensic SQL queries for detecting unauthorized access, data exfiltration, lateral movement, and privilege escalation. Use when investigatin

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
