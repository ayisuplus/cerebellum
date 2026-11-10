---
title: detecting-aws-cloudtrail-anomalies
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-cloud-storage-access-patterns, detecting-anomalous-authentication-patterns, detecting-aws-credential-exposure-with-trufflehog, detecting-aws-iam-privilege-escalation, detecting-cloud-threats-with-guardduty, detecting-compromised-cloud-credentials, detecting-cryptomining-in-cloud, detecting-email-account-compromise, detecting-insider-data-exfiltration-via-dlp, detecting-privilege-escalation-in-kubernetes-pods, detecting-s3-data-exfiltration-attempts, detecting-service-account-abuse, detecting-shadow-api-endpoints, detecting-shadow-it-cloud-usage, detecting-suspicious-oauth-application-consent, implementing-cloud-trail-log-analysis, implementing-cloud-workload-protection, implementing-network-traffic-baselining, performing-cloud-log-forensics-with-athena, performing-cloud-native-threat-hunting-with-aws-detective, performing-user-behavior-analytics]
confidence: low
---

Detect unusual API call patterns in AWS CloudTrail logs using boto3, statistical baselining, and behavioral analysis to identify credential compromise, privilege escalation, and unauthorized resource access.

## Metadata

- **ID:** `detecting-aws-cloudtrail-anomalies`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-aws-cloudtrail-anomalies/SKILL.md`
- **Score:** 22.0
- **Edges:** 21

## Related Skills

- [[detecting-compromised-cloud-credentials]] *(bridge)* — Detecting compromised cloud credentials across AWS, Azure, and GCP by analyzing anomalous API activity, impossible travel patterns, unauthorized resource provisioning, and credential abuse indicators using GuardDuty, Defender for Identity, and SCC Event Threat Detection.

- [[detecting-aws-iam-privilege-escalation]] *(complement)* — Detect AWS IAM privilege escalation paths using boto3 and Cloudsplaining policy analysis to identify overly permissive policies, dangerous permission combinations, and least-privilege violations
- [[detecting-s3-data-exfiltration-attempts]] *(complement)* — Detecting data exfiltration attempts from AWS S3 buckets by analyzing CloudTrail S3 data events, VPC Flow Logs, GuardDuty findings, Amazon Macie alerts, and S3 access patterns to identify unauthorized bulk downloads and cross-account data transfers.

- [[detecting-service-account-abuse]] *(complement)* — Detect abuse of service accounts through anomalous interactive logons, privilege escalation, lateral movement, and unauthorized access patterns.
- [[implementing-cloud-trail-log-analysis]] *(complement)* — Implementing AWS CloudTrail log analysis for security monitoring, threat detection, and forensic investigation using Athena, CloudWatch Logs Insights, and SIEM integration to identify unauthorized access, privilege escalation, and suspicious API activity.

- [[detecting-insider-data-exfiltration-via-dlp]] *(similar)* — Detects insider data exfiltration by analyzing DLP policy violations, file access patterns, upload volume anomalies, and off-hours activity in endpoint and cloud logs. Uses pandas for behavioral analytics and statistical baselines. Use when investigating insider threats or building user behavior ana
- [[analyzing-cloud-storage-access-patterns]] *(complement)* — Detect abnormal access patterns in AWS S3, GCS, and Azure Blob Storage by analyzing CloudTrail Data Events, GCS audit logs, and Azure Storage Analytics. Identifies after-hours bulk downloads, access from new IP addresses, unusual API calls (GetObject spikes), and potential data exfiltration using st
- [[detecting-anomalous-authentication-patterns]] *(complement)* — Detects anomalous authentication patterns using UEBA analytics, statistical baselines, and machine learning models to identify impossible travel, credential stuffing, brute force, password spraying, and compromised account behaviors across authentication logs. Activates for requests involving authen
- [[detecting-aws-credential-exposure-with-trufflehog]] *(similar)* — Detecting exposed AWS credentials in source code repositories, CI/CD pipelines, and configuration files using TruffleHog, git-secrets, and AWS-native detection mechanisms to prevent credential theft and unauthorized account access.

- [[detecting-cloud-threats-with-guardduty]] *(similar)* — This skill teaches security teams how to deploy and operationalize Amazon GuardDuty for continuous threat detection across AWS accounts and workloads. It covers enabling protection plans for S3, EKS, EC2 runtime monitoring, and Lambda, interpreting finding severity levels, and building automated res
- [[detecting-cryptomining-in-cloud]] *(similar)* — This skill teaches security teams how to detect and respond to unauthorized cryptocurrency mining operations in cloud environments. It covers identifying cryptomining indicators through compute usage anomalies, network traffic patterns to mining pools, GuardDuty CryptoCurrency findings, and runtime 
- [[detecting-email-account-compromise]] *(similar)* — Detect compromised O365 and Google Workspace email accounts by analyzing inbox rule creation, suspicious sign-in locations, mail forwarding rules, and unusual API access patterns via Microsoft Graph and audit logs.
- [[detecting-privilege-escalation-in-kubernetes-pods]] *(similar)* — Detect and prevent privilege escalation in Kubernetes pods by monitoring security contexts, capabilities, and syscall patterns with Falco and OPA policies.
- [[detecting-shadow-api-endpoints]] *(similar)* — Discover and inventory shadow API endpoints that operate outside documented specifications using traffic analysis, code scanning, and API discovery platforms.
- [[detecting-shadow-it-cloud-usage]] *(similar)* — Detect unauthorized SaaS and cloud service usage (shadow IT) by analyzing proxy logs, DNS query logs, and netflow data using Python pandas for traffic pattern analysis and domain classification.
- [[detecting-suspicious-oauth-application-consent]] *(similar)* — Detect risky OAuth application consent grants in Azure AD / Microsoft Entra ID using Microsoft Graph API, audit logs, and permission analysis to identify illicit consent grant attacks.
- [[implementing-cloud-workload-protection]] *(similar)* — Implements cloud workload protection using boto3 and google-cloud APIs for runtime security monitoring, process anomaly detection, and file integrity checking on EC2/GCE instances. Scans for cryptomining, reverse shells, and unauthorized binaries. Use when building runtime security controls for clou
- [[implementing-network-traffic-baselining]] *(similar)* — Build network traffic baselines from NetFlow/IPFIX data using Python pandas for statistical analysis, z-score anomaly detection, and hourly/daily traffic pattern profiling
- [[performing-cloud-log-forensics-with-athena]] *(similar)* — Uses AWS Athena to query CloudTrail, VPC Flow Logs, S3 access logs, and ALB logs for forensic investigation. Covers CREATE TABLE DDL with partition projection, forensic SQL queries for detecting unauthorized access, data exfiltration, lateral movement, and privilege escalation. Use when investigatin
- [[performing-cloud-native-threat-hunting-with-aws-detective]] *(similar)* — Hunt for threats in AWS environments using Detective behavior graphs, entity investigation timelines, GuardDuty finding correlation, and automated entity profiling across IAM users, EC2 instances, and IP addresses.
- [[performing-user-behavior-analytics]] *(similar)* — Performs User and Entity Behavior Analytics (UEBA) to detect anomalous user activities including impossible travel, unusual access patterns, privilege abuse, and insider threats using SIEM-based behavioral baselines and statistical analysis. Use when SOC teams need to identify compromised accounts o

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
