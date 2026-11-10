---
title: detecting-service-account-abuse
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-azure-activity-logs-for-threats, analyzing-cloud-storage-access-patterns, analyzing-kubernetes-audit-logs, detecting-anomalous-authentication-patterns, detecting-aws-cloudtrail-anomalies, detecting-aws-iam-privilege-escalation, detecting-azure-lateral-movement, detecting-container-escape-attempts, detecting-credential-dumping-techniques, detecting-email-account-compromise, detecting-entra-offensive-tools-in-graph-logs, detecting-evasion-techniques-in-endpoint-logs, detecting-insider-data-exfiltration-via-dlp, detecting-kerberoasting-attacks, detecting-lateral-movement-with-zeek, detecting-living-off-the-land-attacks, detecting-mimikatz-execution-patterns, detecting-misconfigured-azure-storage, detecting-pass-the-hash-attacks, detecting-privilege-escalation-in-kubernetes-pods, detecting-rdp-brute-force-attacks, detecting-s3-data-exfiltration-attempts, detecting-shadow-it-cloud-usage, detecting-suspicious-oauth-application-consent, hunting-credential-stuffing-attacks, hunting-for-unusual-service-installations, investigating-insider-threat-indicators, performing-brand-monitoring-for-impersonation, performing-user-behavior-analytics]
confidence: low
---

Detect abuse of service accounts through anomalous interactive logons, privilege escalation, lateral movement, and unauthorized access patterns.

## Metadata

- **ID:** `detecting-service-account-abuse`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-service-account-abuse/SKILL.md`
- **Score:** 31.0
- **Edges:** 29

## Related Skills

- [[analyzing-cloud-storage-access-patterns]] *(similar)* — Detect abnormal access patterns in AWS S3, GCS, and Azure Blob Storage by analyzing CloudTrail Data Events, GCS audit logs, and Azure Storage Analytics. Identifies after-hours bulk downloads, access from new IP addresses, unusual API calls (GetObject spikes), and potential data exfiltration using st
- [[detecting-credential-dumping-techniques]] *(similar)* — Detect LSASS credential dumping, SAM database extraction, and NTDS.dit theft using Sysmon Event ID 10, Windows Security logs, and SIEM correlation rules
- [[detecting-suspicious-oauth-application-consent]] *(similar)* — Detect risky OAuth application consent grants in Azure AD / Microsoft Entra ID using Microsoft Graph API, audit logs, and permission analysis to identify illicit consent grant attacks.
- [[hunting-credential-stuffing-attacks]] *(similar)* — Detects credential stuffing attacks by analyzing authentication logs for login velocity anomalies, ASN diversity, password spray patterns, and geographic distribution of failed logins. Uses statistical analysis on Splunk or raw log data. Use when investigating account takeover campaigns or building 
- [[performing-user-behavior-analytics]] *(similar)* — Performs User and Entity Behavior Analytics (UEBA) to detect anomalous user activities including impossible travel, unusual access patterns, privilege abuse, and insider threats using SIEM-based behavioral baselines and statistical analysis. Use when SOC teams need to identify compromised accounts o
- [[detecting-anomalous-authentication-patterns]] *(complement)* — Detects anomalous authentication patterns using UEBA analytics, statistical baselines, and machine learning models to identify impossible travel, credential stuffing, brute force, password spraying, and compromised account behaviors across authentication logs. Activates for requests involving authen
- [[detecting-aws-cloudtrail-anomalies]] *(complement)* — Detect unusual API call patterns in AWS CloudTrail logs using boto3, statistical baselining, and behavioral analysis to identify credential compromise, privilege escalation, and unauthorized resource access.
- [[detecting-azure-lateral-movement]] *(complement)* — Detect lateral movement in Azure AD/Entra ID environments using Microsoft Graph API audit logs, Azure Sentinel KQL hunting queries, and sign-in anomaly correlation to identify privilege escalation, token theft, and cross-tenant pivoting.
- [[detecting-email-account-compromise]] *(complement)* — Detect compromised O365 and Google Workspace email accounts by analyzing inbox rule creation, suspicious sign-in locations, mail forwarding rules, and unusual API access patterns via Microsoft Graph and audit logs.
- [[detecting-kerberoasting-attacks]] *(complement)* — Detect Kerberoasting attacks by monitoring for anomalous Kerberos TGS requests targeting service accounts with SPNs for offline password cracking.
- [[analyzing-azure-activity-logs-for-threats]] *(similar)* — Queries Azure Monitor activity logs and sign-in logs via azure-monitor-query to detect suspicious administrative operations, impossible travel, privilege escalation, and resource modifications. Builds KQL queries for threat hunting in Azure environments. Use when investigating suspicious Azure tenan
- [[analyzing-kubernetes-audit-logs]] *(similar)* — Parses Kubernetes API server audit logs (JSON lines) to detect exec-into-pod, secret access, RBAC modifications, privileged pod creation, and anonymous API access. Builds threat detection rules from audit event patterns. Use when investigating Kubernetes cluster compromise or building k8s-specific S
- [[detecting-aws-iam-privilege-escalation]] *(similar)* — Detect AWS IAM privilege escalation paths using boto3 and Cloudsplaining policy analysis to identify overly permissive policies, dangerous permission combinations, and least-privilege violations
- [[detecting-container-escape-attempts]] *(similar)* — Container escape is a critical attack technique where an adversary breaks out of container isolation to access the host system or other containers. Detection involves monitoring for escape indicators
- [[detecting-entra-offensive-tools-in-graph-logs]] *(similar)* — Hunt AADGraphActivityLogs and MicrosoftGraphActivityLogs in Microsoft Sentinel/Log Analytics for fingerprints of offensive Entra ID tools such as ROADtools, AADInternals, and AzureHound.
- [[detecting-evasion-techniques-in-endpoint-logs]] *(similar)* — Detects defense evasion techniques used by adversaries in endpoint logs including log tampering, timestomping, process injection, and security tool disabling. Use when investigating suspicious endpoint behavior, building detection rules for evasion tactics, or conducting threat hunting for stealthy 
- [[detecting-insider-data-exfiltration-via-dlp]] *(similar)* — Detects insider data exfiltration by analyzing DLP policy violations, file access patterns, upload volume anomalies, and off-hours activity in endpoint and cloud logs. Uses pandas for behavioral analytics and statistical baselines. Use when investigating insider threats or building user behavior ana
- [[detecting-lateral-movement-with-zeek]] *(similar)* — Detect lateral movement in network traffic using Zeek (formerly Bro) log analysis. Parses conn.log, smb_mapping.log, smb_files.log, dce_rpc.log, kerberos.log, and ntlm.log to identify SMB file transfers, NTLM account spray activity, remote service execution, and anomalous internal connections.

- [[detecting-living-off-the-land-attacks]] *(similar)* — Detect abuse of legitimate Windows binaries (LOLBins) used for living off the land attacks. Monitors process creation, command-line arguments, and parent-child relationships to identify suspicious LOLBin execution patterns.

- [[detecting-mimikatz-execution-patterns]] *(similar)* — Detect Mimikatz execution through command-line patterns, LSASS access signatures, binary indicators, and in-memory detection of known modules.
- [[detecting-misconfigured-azure-storage]] *(similar)* — Detecting misconfigured Azure Storage accounts including publicly accessible blob containers, missing encryption settings, overly permissive SAS tokens, disabled logging, and network access violations using Azure CLI, PowerShell, and Microsoft Defender for Storage.

- [[detecting-pass-the-hash-attacks]] *(similar)* — Detect Pass-the-Hash attacks by analyzing NTLM authentication patterns, identifying Type 3 logons with NTLM where Kerberos is expected, and correlating with credential dumping.
- [[detecting-privilege-escalation-in-kubernetes-pods]] *(similar)* — Detect and prevent privilege escalation in Kubernetes pods by monitoring security contexts, capabilities, and syscall patterns with Falco and OPA policies.
- [[detecting-rdp-brute-force-attacks]] *(similar)* — Detect RDP brute force attacks by analyzing Windows Security Event Logs for failed authentication patterns (Event ID 4625), successful logons after failures (Event ID 4624), NLA failures, and source IP frequency analysis.
- [[detecting-s3-data-exfiltration-attempts]] *(similar)* — Detecting data exfiltration attempts from AWS S3 buckets by analyzing CloudTrail S3 data events, VPC Flow Logs, GuardDuty findings, Amazon Macie alerts, and S3 access patterns to identify unauthorized bulk downloads and cross-account data transfers.

- [[detecting-shadow-it-cloud-usage]] *(similar)* — Detect unauthorized SaaS and cloud service usage (shadow IT) by analyzing proxy logs, DNS query logs, and netflow data using Python pandas for traffic pattern analysis and domain classification.
- [[hunting-for-unusual-service-installations]] *(similar)* — Detect suspicious Windows service installations (MITRE ATT&CK T1543.003) by parsing System event logs for Event ID 7045, analyzing service binary paths, and identifying indicators of persistence mechanisms.
- [[investigating-insider-threat-indicators]] *(similar)* — Investigates insider threat indicators including data exfiltration attempts, unauthorized access patterns, policy violations, and pre-departure behaviors using SIEM analytics, DLP alerts, and HR data correlation. Use when SOC teams receive insider threat referrals from HR, detect anomalous data move
- [[performing-brand-monitoring-for-impersonation]] *(similar)* — Monitor for brand impersonation attacks across domains, social media, mobile apps, and dark web channels to detect phishing campaigns, fake sites, and unauthorized brand usage targeting your organization.

## See Also

- [[abusing-dpapi-for-credential-access]] — Anthropic-Cybersecurity-Skills
- [[abusing-shadow-credentials-for-privesc]] — Anthropic-Cybersecurity-Skills
- [[achieving-cmmc-level-2-compliance]] — Anthropic-Cybersecurity-Skills
- [[acquiring-disk-image-with-dd-and-dcfldd]] — Anthropic-Cybersecurity-Skills
- [[analyzing-active-directory-acl-abuse]] — Anthropic-Cybersecurity-Skills
- [[analyzing-android-malware-with-apktool]] — Anthropic-Cybersecurity-Skills
- [[analyzing-api-gateway-access-logs]] — Anthropic-Cybersecurity-Skills
- [[analyzing-apt-group-with-mitre-navigator]] — Anthropic-Cybersecurity-Skills
- [[analyzing-bootkit-and-rootkit-samples]] — Anthropic-Cybersecurity-Skills
- [[analyzing-campaign-attribution-evidence]] — Anthropic-Cybersecurity-Skills
