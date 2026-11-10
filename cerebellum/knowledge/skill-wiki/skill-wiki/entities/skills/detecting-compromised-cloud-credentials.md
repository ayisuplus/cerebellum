---
title: detecting-compromised-cloud-credentials
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-api-gateway-access-logs, deploying-cloud-deception-with-decoy-resources, detecting-aws-cloudtrail-anomalies, detecting-azure-service-principal-abuse, detecting-business-email-compromise-with-ai, detecting-insider-threat-behaviors, detecting-insider-threat-with-ueba, detecting-model-extraction-attacks, detecting-oauth-token-theft, detecting-serverless-function-injection, detecting-suspicious-powershell-execution, emulating-cloud-attacks-with-stratus-red-team, hunting-for-data-exfiltration-indicators, hunting-for-living-off-the-cloud-techniques, performing-active-directory-compromise-investigation]
confidence: medium
---

Detecting compromised cloud credentials across AWS, Azure, and GCP by analyzing anomalous API activity, impossible travel patterns, unauthorized resource provisioning, and credential abuse indicators using GuardDuty, Defender for Identity, and SCC Event Threat Detection.

## Metadata

- **ID:** `detecting-compromised-cloud-credentials`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-compromised-cloud-credentials/SKILL.md`
- **Score:** 54.0
- **Edges:** 15

## Related Skills

- [[detecting-insider-threat-with-ueba]] *(similar)* — Implement User and Entity Behavior Analytics using Elasticsearch/OpenSearch to build behavioral baselines, calculate anomaly scores, perform peer group analysis, and detect insider threat indicators such as data exfiltration, privilege abuse, and unauthorized access patterns.
- [[detecting-oauth-token-theft]] *(similar)* — Detects and responds to OAuth token theft and replay attacks in cloud environments, focusing on Microsoft Entra ID (Azure AD) token protection, conditional access policies, and sign-in anomaly detection. Covers access token theft, refresh token replay, Primary Refresh Token (PRT) abuse, and pass-the
- [[detecting-serverless-function-injection]] *(similar)* — Detects and prevents code injection attacks targeting serverless functions (AWS Lambda, Azure Functions, Google Cloud Functions) through event source poisoning, malicious layer injection, runtime command execution, and IAM privilege escalation via function modification. The analyst combines static a
- [[emulating-cloud-attacks-with-stratus-red-team]] *(similar)* — Detonate granular AWS, Azure, GCP, and Kubernetes attack techniques to validate detections with Stratus Red Team.
- [[performing-active-directory-compromise-investigation]] *(similar)* — Investigate Active Directory compromise by analyzing authentication logs, replication metadata, Group Policy changes, and Kerberos ticket anomalies to identify attacker persistence and lateral movement paths.
- [[detecting-aws-cloudtrail-anomalies]] *(bridge)* — Detect unusual API call patterns in AWS CloudTrail logs using boto3, statistical baselining, and behavioral analysis to identify credential compromise, privilege escalation, and unauthorized resource access.
- [[detecting-azure-service-principal-abuse]] *(complement)* — Detect and investigate Azure service principal abuse including privilege escalation, credential compromise, admin consent bypass, and unauthorized enumeration in Microsoft Entra ID environments.
- [[analyzing-api-gateway-access-logs]] *(similar)* — Parses API Gateway access logs (AWS API Gateway, Kong, Nginx) to detect BOLA/IDOR attacks, rate limit bypass, credential scanning, and injection attempts. Uses pandas for statistical analysis of request patterns and anomaly detection. Use when investigating API abuse or building API-specific threat 
- [[deploying-cloud-deception-with-decoy-resources]] *(similar)* — Deploy cloud-native deception across AWS, Azure, and GCP using decoy (honey) resources whose only purpose is to generate a high-fidelity alert the instant an attacker touches them: canary IAM access keys, permission-less decoy users/roles/service principals, honey object-storage buckets, and decoy s
- [[detecting-business-email-compromise-with-ai]] *(similar)* — Deploy AI and NLP-powered detection systems to identify business email compromise attacks by analyzing writing style, behavioral patterns, and contextual anomalies that evade traditional rule-based filters.
- [[detecting-insider-threat-behaviors]] *(similar)* — Detect insider threat behavioral indicators including unusual data access, off-hours activity, mass file downloads, privilege abuse, and resignation-correlated data theft.
- [[detecting-model-extraction-attacks]] *(similar)* — Detect model stealing, model inversion, and membership inference performed through inference-API abuse by monitoring query patterns, applying output perturbation, and red-teaming your own model's extractability.
- [[detecting-suspicious-powershell-execution]] *(similar)* — Detect suspicious PowerShell execution patterns including encoded commands, download cradles, AMSI bypass attempts, and constrained language mode evasion.
- [[hunting-for-data-exfiltration-indicators]] *(similar)* — Hunt for data exfiltration through network traffic analysis, detecting unusual data flows, DNS tunneling, cloud storage uploads, and encrypted channel abuse.
- [[hunting-for-living-off-the-cloud-techniques]] *(similar)* — Hunt for adversary abuse of legitimate cloud services for C2, data staging, and exfiltration including abuse of Azure, AWS, GCP services, and SaaS platforms.

## See Also

- [[abusing-dpapi-for-credential-access]] — Anthropic-Cybersecurity-Skills
- [[abusing-shadow-credentials-for-privesc]] — Anthropic-Cybersecurity-Skills
- [[achieving-cmmc-level-2-compliance]] — Anthropic-Cybersecurity-Skills
- [[acquiring-disk-image-with-dd-and-dcfldd]] — Anthropic-Cybersecurity-Skills
- [[analyzing-active-directory-acl-abuse]] — Anthropic-Cybersecurity-Skills
- [[analyzing-android-malware-with-apktool]] — Anthropic-Cybersecurity-Skills
- [[analyzing-apt-group-with-mitre-navigator]] — Anthropic-Cybersecurity-Skills
- [[analyzing-azure-activity-logs-for-threats]] — Anthropic-Cybersecurity-Skills
- [[analyzing-bootkit-and-rootkit-samples]] — Anthropic-Cybersecurity-Skills
- [[analyzing-campaign-attribution-evidence]] — Anthropic-Cybersecurity-Skills
