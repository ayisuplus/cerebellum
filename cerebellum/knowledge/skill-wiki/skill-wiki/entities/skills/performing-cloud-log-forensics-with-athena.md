---
title: performing-cloud-log-forensics-with-athena
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-cloud-storage-access-patterns, detecting-aws-cloudtrail-anomalies, detecting-aws-iam-privilege-escalation, detecting-s3-data-exfiltration-attempts, detecting-shadow-it-cloud-usage, implementing-cloud-trail-log-analysis, performing-cloud-native-threat-hunting-with-aws-detective]
confidence: medium
---

Uses AWS Athena to query CloudTrail, VPC Flow Logs, S3 access logs, and ALB logs for forensic investigation. Covers CREATE TABLE DDL with partition projection, forensic SQL queries for detecting unauthorized access, data exfiltration, lateral movement, and privilege escalation. Use when investigatin

## Metadata

- **ID:** `performing-cloud-log-forensics-with-athena`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/performing-cloud-log-forensics-with-athena/SKILL.md`
- **Score:** 42.0
- **Edges:** 7

## Related Skills

- [[analyzing-cloud-storage-access-patterns]] *(similar)* — Detect abnormal access patterns in AWS S3, GCS, and Azure Blob Storage by analyzing CloudTrail Data Events, GCS audit logs, and Azure Storage Analytics. Identifies after-hours bulk downloads, access from new IP addresses, unusual API calls (GetObject spikes), and potential data exfiltration using st
- [[detecting-aws-cloudtrail-anomalies]] *(similar)* — Detect unusual API call patterns in AWS CloudTrail logs using boto3, statistical baselining, and behavioral analysis to identify credential compromise, privilege escalation, and unauthorized resource access.
- [[detecting-aws-iam-privilege-escalation]] *(similar)* — Detect AWS IAM privilege escalation paths using boto3 and Cloudsplaining policy analysis to identify overly permissive policies, dangerous permission combinations, and least-privilege violations
- [[detecting-shadow-it-cloud-usage]] *(similar)* — Detect unauthorized SaaS and cloud service usage (shadow IT) by analyzing proxy logs, DNS query logs, and netflow data using Python pandas for traffic pattern analysis and domain classification.
- [[performing-cloud-native-threat-hunting-with-aws-detective]] *(similar)* — Hunt for threats in AWS environments using Detective behavior graphs, entity investigation timelines, GuardDuty finding correlation, and automated entity profiling across IAM users, EC2 instances, and IP addresses.
- [[implementing-cloud-trail-log-analysis]] *(complement)* — Implementing AWS CloudTrail log analysis for security monitoring, threat detection, and forensic investigation using Athena, CloudWatch Logs Insights, and SIEM integration to identify unauthorized access, privilege escalation, and suspicious API activity.

- [[detecting-s3-data-exfiltration-attempts]] *(similar)* — Detecting data exfiltration attempts from AWS S3 buckets by analyzing CloudTrail S3 data events, VPC Flow Logs, GuardDuty findings, Amazon Macie alerts, and S3 access patterns to identify unauthorized bulk downloads and cross-account data transfers.


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
