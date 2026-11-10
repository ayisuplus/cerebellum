---
title: detecting-shadow-it-cloud-usage
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-cloud-storage-access-patterns, analyzing-network-flow-data-with-netflow, analyzing-typosquatting-domains-with-dnstwist, detecting-aws-cloudtrail-anomalies, detecting-insider-data-exfiltration-via-dlp, detecting-s3-data-exfiltration-attempts, detecting-service-account-abuse, detecting-shadow-api-endpoints, hunting-for-domain-fronting-c2-traffic, implementing-network-traffic-baselining, performing-cloud-log-forensics-with-athena]
confidence: low
---

Detect unauthorized SaaS and cloud service usage (shadow IT) by analyzing proxy logs, DNS query logs, and netflow data using Python pandas for traffic pattern analysis and domain classification.

## Metadata

- **ID:** `detecting-shadow-it-cloud-usage`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-shadow-it-cloud-usage/SKILL.md`
- **Score:** 27.0
- **Edges:** 11

## Related Skills

- [[analyzing-cloud-storage-access-patterns]] *(similar)* — Detect abnormal access patterns in AWS S3, GCS, and Azure Blob Storage by analyzing CloudTrail Data Events, GCS audit logs, and Azure Storage Analytics. Identifies after-hours bulk downloads, access from new IP addresses, unusual API calls (GetObject spikes), and potential data exfiltration using st
- [[analyzing-network-flow-data-with-netflow]] *(similar)* — Parse NetFlow v9 and IPFIX records to detect volumetric anomalies, port scanning, data exfiltration, and C2 beaconing patterns. Uses the Python netflow library to decode flow records, builds traffic baselines, and applies statistical analysis to identify flows with abnormal byte counts, connection d
- [[detecting-aws-cloudtrail-anomalies]] *(similar)* — Detect unusual API call patterns in AWS CloudTrail logs using boto3, statistical baselining, and behavioral analysis to identify credential compromise, privilege escalation, and unauthorized resource access.
- [[detecting-service-account-abuse]] *(similar)* — Detect abuse of service accounts through anomalous interactive logons, privilege escalation, lateral movement, and unauthorized access patterns.
- [[implementing-network-traffic-baselining]] *(similar)* — Build network traffic baselines from NetFlow/IPFIX data using Python pandas for statistical analysis, z-score anomaly detection, and hourly/daily traffic pattern profiling
- [[analyzing-typosquatting-domains-with-dnstwist]] *(similar)* — Detect typosquatting, homograph phishing, and brand impersonation domains using dnstwist to generate domain permutations and identify registered lookalike domains targeting your organization.
- [[detecting-insider-data-exfiltration-via-dlp]] *(similar)* — Detects insider data exfiltration by analyzing DLP policy violations, file access patterns, upload volume anomalies, and off-hours activity in endpoint and cloud logs. Uses pandas for behavioral analytics and statistical baselines. Use when investigating insider threats or building user behavior ana
- [[detecting-s3-data-exfiltration-attempts]] *(similar)* — Detecting data exfiltration attempts from AWS S3 buckets by analyzing CloudTrail S3 data events, VPC Flow Logs, GuardDuty findings, Amazon Macie alerts, and S3 access patterns to identify unauthorized bulk downloads and cross-account data transfers.

- [[detecting-shadow-api-endpoints]] *(similar)* — Discover and inventory shadow API endpoints that operate outside documented specifications using traffic analysis, code scanning, and API discovery platforms.
- [[hunting-for-domain-fronting-c2-traffic]] *(similar)* — Detect domain fronting C2 traffic by analyzing SNI vs HTTP Host header mismatches in proxy logs and TLS certificate discrepancies using pyOpenSSL for certificate inspection
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
