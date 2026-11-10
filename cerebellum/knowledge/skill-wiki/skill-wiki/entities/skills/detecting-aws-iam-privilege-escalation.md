---
title: detecting-aws-iam-privilege-escalation
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [detecting-aws-cloudtrail-anomalies, detecting-aws-credential-exposure-with-trufflehog, detecting-privilege-escalation-in-kubernetes-pods, detecting-s3-data-exfiltration-attempts, detecting-service-account-abuse, detecting-suspicious-oauth-application-consent, implementing-cloud-trail-log-analysis, performing-aws-privilege-escalation-assessment, performing-cloud-log-forensics-with-athena, performing-cloud-native-threat-hunting-with-aws-detective]
confidence: low
---

Detect AWS IAM privilege escalation paths using boto3 and Cloudsplaining policy analysis to identify overly permissive policies, dangerous permission combinations, and least-privilege violations

## Metadata

- **ID:** `detecting-aws-iam-privilege-escalation`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-aws-iam-privilege-escalation/SKILL.md`
- **Score:** 30.0
- **Edges:** 10

## Related Skills

- [[detecting-aws-credential-exposure-with-trufflehog]] *(similar)* — Detecting exposed AWS credentials in source code repositories, CI/CD pipelines, and configuration files using TruffleHog, git-secrets, and AWS-native detection mechanisms to prevent credential theft and unauthorized account access.

- [[detecting-privilege-escalation-in-kubernetes-pods]] *(similar)* — Detect and prevent privilege escalation in Kubernetes pods by monitoring security contexts, capabilities, and syscall patterns with Falco and OPA policies.
- [[detecting-s3-data-exfiltration-attempts]] *(similar)* — Detecting data exfiltration attempts from AWS S3 buckets by analyzing CloudTrail S3 data events, VPC Flow Logs, GuardDuty findings, Amazon Macie alerts, and S3 access patterns to identify unauthorized bulk downloads and cross-account data transfers.

- [[detecting-service-account-abuse]] *(similar)* — Detect abuse of service accounts through anomalous interactive logons, privilege escalation, lateral movement, and unauthorized access patterns.
- [[implementing-cloud-trail-log-analysis]] *(similar)* — Implementing AWS CloudTrail log analysis for security monitoring, threat detection, and forensic investigation using Athena, CloudWatch Logs Insights, and SIEM integration to identify unauthorized access, privilege escalation, and suspicious API activity.

- [[performing-aws-privilege-escalation-assessment]] *(bridge)* — Performing authorized privilege escalation assessments in AWS environments to identify IAM misconfigurations that allow users or roles to elevate their permissions using Pacu, CloudFox, Principal Mapper, and manual IAM policy analysis techniques.

- [[detecting-aws-cloudtrail-anomalies]] *(complement)* — Detect unusual API call patterns in AWS CloudTrail logs using boto3, statistical baselining, and behavioral analysis to identify credential compromise, privilege escalation, and unauthorized resource access.
- [[detecting-suspicious-oauth-application-consent]] *(similar)* — Detect risky OAuth application consent grants in Azure AD / Microsoft Entra ID using Microsoft Graph API, audit logs, and permission analysis to identify illicit consent grant attacks.
- [[performing-cloud-log-forensics-with-athena]] *(similar)* — Uses AWS Athena to query CloudTrail, VPC Flow Logs, S3 access logs, and ALB logs for forensic investigation. Covers CREATE TABLE DDL with partition projection, forensic SQL queries for detecting unauthorized access, data exfiltration, lateral movement, and privilege escalation. Use when investigatin
- [[performing-cloud-native-threat-hunting-with-aws-detective]] *(similar)* — Hunt for threats in AWS environments using Detective behavior graphs, entity investigation timelines, GuardDuty finding correlation, and automated entity profiling across IAM users, EC2 instances, and IP addresses.

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
