---
title: detecting-azure-service-principal-abuse
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-active-directory-acl-abuse, attacking-oauth-with-device-code-phishing, auditing-entra-id-with-aadinternals, auditing-kubernetes-cluster-rbac, detecting-api-enumeration-attacks, detecting-azure-lateral-movement, detecting-compromised-cloud-credentials, detecting-dll-sideloading-attacks, detecting-insider-threat-behaviors, detecting-insider-threat-with-ueba, detecting-oauth-token-theft, detecting-privilege-escalation-attempts, detecting-secure-boot-bypass, detecting-serverless-function-injection, detecting-supply-chain-attacks-in-ci-cd, detecting-suspicious-powershell-execution, detecting-t1548-abuse-elevation-control-mechanism, exploiting-constrained-delegation-abuse, hunting-for-living-off-the-cloud-techniques, hunting-for-t1098-account-manipulation, hunting-saas-sso-token-abuse, implementing-passwordless-auth-with-microsoft-entra, mapping-attack-paths-with-bloodhound-ce, performing-active-directory-compromise-investigation, performing-container-escape-detection, post-exploiting-microsoft-graph-with-graphrunner]
confidence: low
---

Detect and investigate Azure service principal abuse including privilege escalation, credential compromise, admin consent bypass, and unauthorized enumeration in Microsoft Entra ID environments.

## Metadata

- **ID:** `detecting-azure-service-principal-abuse`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-azure-service-principal-abuse/SKILL.md`
- **Score:** 35.0
- **Edges:** 26

## Related Skills

- [[detecting-compromised-cloud-credentials]] *(complement)* — Detecting compromised cloud credentials across AWS, Azure, and GCP by analyzing anomalous API activity, impossible travel patterns, unauthorized resource provisioning, and credential abuse indicators using GuardDuty, Defender for Identity, and SCC Event Threat Detection.

- [[detecting-oauth-token-theft]] *(complement)* — Detects and responds to OAuth token theft and replay attacks in cloud environments, focusing on Microsoft Entra ID (Azure AD) token protection, conditional access policies, and sign-in anomaly detection. Covers access token theft, refresh token replay, Primary Refresh Token (PRT) abuse, and pass-the
- [[detecting-privilege-escalation-attempts]] *(complement)* — Detect privilege escalation attempts including token manipulation, UAC bypass, unquoted service paths, kernel exploits, and sudo/doas abuse across Windows and Linux.
- [[analyzing-active-directory-acl-abuse]] *(similar)* — Detect dangerous ACL misconfigurations in Active Directory using ldap3 to identify GenericAll, WriteDACL, and WriteOwner abuse paths
- [[hunting-saas-sso-token-abuse]] *(similar)* — Detect SSO and OAuth token replay and SaaS lateral movement.
- [[detecting-azure-lateral-movement]] *(bridge)* — Detect lateral movement in Azure AD/Entra ID environments using Microsoft Graph API audit logs, Azure Sentinel KQL hunting queries, and sign-in anomaly correlation to identify privilege escalation, token theft, and cross-tenant pivoting.
- [[auditing-entra-id-with-aadinternals]] *(complement)* — Run Microsoft Entra ID tenant reconnaissance, token acquisition and manipulation, and federation backdoor testing with the AADInternals PowerShell toolkit to validate identity-attack resilience.
- [[attacking-oauth-with-device-code-phishing]] *(similar)* — Run OAuth 2.0 device-code and illicit-consent phishing against Microsoft Entra ID to steal access and refresh tokens, bypass MFA, and pivot across Microsoft 365 services.
- [[auditing-kubernetes-cluster-rbac]] *(similar)* — Auditing Kubernetes cluster RBAC configurations to identify overly permissive roles, wildcard permissions, dangerous ClusterRoleBindings, service account abuse, and privilege escalation paths using kubectl, rbac-tool, KubiScan, and Kubeaudit.

- [[detecting-api-enumeration-attacks]] *(similar)* — Detect and prevent API enumeration attacks including BOLA and IDOR exploitation by monitoring sequential identifier access patterns and authorization failures.
- [[detecting-dll-sideloading-attacks]] *(similar)* — Detect DLL side-loading attacks where adversaries place malicious DLLs alongside legitimate applications to hijack execution flow for defense evasion.
- [[detecting-insider-threat-behaviors]] *(similar)* — Detect insider threat behavioral indicators including unusual data access, off-hours activity, mass file downloads, privilege abuse, and resignation-correlated data theft.
- [[detecting-insider-threat-with-ueba]] *(similar)* — Implement User and Entity Behavior Analytics using Elasticsearch/OpenSearch to build behavioral baselines, calculate anomaly scores, perform peer group analysis, and detect insider threat indicators such as data exfiltration, privilege abuse, and unauthorized access patterns.
- [[detecting-secure-boot-bypass]] *(similar)* — Detect bootkits such as BlackLotus and Bootkitty and Secure Boot bypass via DBX and binary checks.
- [[detecting-serverless-function-injection]] *(similar)* — Detects and prevents code injection attacks targeting serverless functions (AWS Lambda, Azure Functions, Google Cloud Functions) through event source poisoning, malicious layer injection, runtime command execution, and IAM privilege escalation via function modification. The analyst combines static a
- [[detecting-supply-chain-attacks-in-ci-cd]] *(similar)* — Scans GitHub Actions workflows and CI/CD pipeline configurations for supply chain attack vectors including unpinned actions, script injection via expressions, dependency confusion, and secrets exposure. Uses PyGithub and YAML parsing for automated audit. Use when hardening CI/CD pipelines or investi
- [[detecting-suspicious-powershell-execution]] *(similar)* — Detect suspicious PowerShell execution patterns including encoded commands, download cradles, AMSI bypass attempts, and constrained language mode evasion.
- [[detecting-t1548-abuse-elevation-control-mechanism]] *(similar)* — Detect abuse of elevation control mechanisms including UAC bypass, sudo exploitation, and setuid/setgid manipulation by monitoring registry modifications, process elevation flags, and unusual parent-child process relationships.
- [[exploiting-constrained-delegation-abuse]] *(similar)* — Exploit Kerberos Constrained Delegation misconfigurations in Active Directory to impersonate privileged users via S4U2self and S4U2proxy extensions for lateral movement and privilege escalation.
- [[hunting-for-living-off-the-cloud-techniques]] *(similar)* — Hunt for adversary abuse of legitimate cloud services for C2, data staging, and exfiltration including abuse of Azure, AWS, GCP services, and SaaS platforms.
- [[hunting-for-t1098-account-manipulation]] *(similar)* — Hunt for MITRE ATT&CK T1098 account manipulation including shadow admin creation, SID history injection, group membership changes, and credential modifications using Windows Security Event Logs.
- [[implementing-passwordless-auth-with-microsoft-entra]] *(similar)* — Implements passwordless authentication using Microsoft Entra ID with FIDO2 security keys, Windows Hello for Business, Microsoft Authenticator passkeys, and certificate-based authentication to eliminate password-based attacks. Activates for requests involving passwordless deployment, FIDO2 passkey co
- [[mapping-attack-paths-with-bloodhound-ce]] *(similar)* — Collect Active Directory data with SharpHound and Entra ID data with AzureHound, ingest into BloodHound Community Edition, and analyze on-prem, cloud, and hybrid attack paths with built-in queries and custom Cypher.
- [[performing-active-directory-compromise-investigation]] *(similar)* — Investigate Active Directory compromise by analyzing authentication logs, replication metadata, Group Policy changes, and Kerberos ticket anomalies to identify attacker persistence and lateral movement paths.
- [[performing-container-escape-detection]] *(similar)* — Detects container escape attempts by analyzing namespace configurations, privileged container checks, dangerous capability assignments, and host path mounts using the kubernetes Python client. Identifies CVE-2022-0492 style escapes via cgroup abuse. Use when auditing container security posture or in
- [[post-exploiting-microsoft-graph-with-graphrunner]] *(similar)* — Perform recon, persistence, privilege escalation, and data search via the Microsoft Graph API using GraphRunner.

## See Also

- [[abusing-dpapi-for-credential-access]] — Anthropic-Cybersecurity-Skills
- [[abusing-shadow-credentials-for-privesc]] — Anthropic-Cybersecurity-Skills
- [[achieving-cmmc-level-2-compliance]] — Anthropic-Cybersecurity-Skills
- [[acquiring-disk-image-with-dd-and-dcfldd]] — Anthropic-Cybersecurity-Skills
- [[analyzing-android-malware-with-apktool]] — Anthropic-Cybersecurity-Skills
- [[analyzing-api-gateway-access-logs]] — Anthropic-Cybersecurity-Skills
- [[analyzing-apt-group-with-mitre-navigator]] — Anthropic-Cybersecurity-Skills
- [[analyzing-azure-activity-logs-for-threats]] — Anthropic-Cybersecurity-Skills
- [[analyzing-bootkit-and-rootkit-samples]] — Anthropic-Cybersecurity-Skills
- [[analyzing-campaign-attribution-evidence]] — Anthropic-Cybersecurity-Skills
