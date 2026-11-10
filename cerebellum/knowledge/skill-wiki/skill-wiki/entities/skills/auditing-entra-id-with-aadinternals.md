---
title: auditing-entra-id-with-aadinternals
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [attacking-entra-id-with-roadtools, attacking-oauth-with-device-code-phishing, auditing-azure-active-directory-configuration, detecting-azure-service-principal-abuse, detecting-oauth-token-theft, exploiting-active-directory-with-bloodhound, implementing-passwordless-auth-with-microsoft-entra, mapping-attack-paths-with-bloodhound-ce, performing-active-directory-compromise-investigation, performing-active-directory-forest-trust-attack, performing-active-directory-vulnerability-assessment, post-exploiting-microsoft-graph-with-graphrunner]
confidence: low
---

Run Microsoft Entra ID tenant reconnaissance, token acquisition and manipulation, and federation backdoor testing with the AADInternals PowerShell toolkit to validate identity-attack resilience.

## Metadata

- **ID:** `auditing-entra-id-with-aadinternals`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/auditing-entra-id-with-aadinternals/SKILL.md`
- **Score:** 38.0
- **Edges:** 12

## Related Skills

- [[detecting-azure-service-principal-abuse]] *(complement)* — Detect and investigate Azure service principal abuse including privilege escalation, credential compromise, admin consent bypass, and unauthorized enumeration in Microsoft Entra ID environments.
- [[exploiting-active-directory-with-bloodhound]] *(similar)* — BloodHound is a graph-based Active Directory reconnaissance tool that uses graph theory to reveal hidden and unintended relationships within AD environments. Red teams use BloodHound to identify attac
- [[mapping-attack-paths-with-bloodhound-ce]] *(similar)* — Collect Active Directory data with SharpHound and Entra ID data with AzureHound, ingest into BloodHound Community Edition, and analyze on-prem, cloud, and hybrid attack paths with built-in queries and custom Cypher.
- [[performing-active-directory-compromise-investigation]] *(similar)* — Investigate Active Directory compromise by analyzing authentication logs, replication metadata, Group Policy changes, and Kerberos ticket anomalies to identify attacker persistence and lateral movement paths.
- [[post-exploiting-microsoft-graph-with-graphrunner]] *(similar)* — Perform recon, persistence, privilege escalation, and data search via the Microsoft Graph API using GraphRunner.
- [[auditing-azure-active-directory-configuration]] *(bridge)* — Auditing Microsoft Entra ID (Azure Active Directory) configuration to identify risky authentication policies, overly permissive role assignments, stale accounts, conditional access gaps, and guest user risks using AzureAD PowerShell, Microsoft Graph API, and ScoutSuite.

- [[attacking-entra-id-with-roadtools]] *(complement)* — Enumerate Entra ID with ROADrecon and acquire and exchange tokens with roadtx.
- [[attacking-oauth-with-device-code-phishing]] *(similar)* — Run OAuth 2.0 device-code and illicit-consent phishing against Microsoft Entra ID to steal access and refresh tokens, bypass MFA, and pivot across Microsoft 365 services.
- [[detecting-oauth-token-theft]] *(similar)* — Detects and responds to OAuth token theft and replay attacks in cloud environments, focusing on Microsoft Entra ID (Azure AD) token protection, conditional access policies, and sign-in anomaly detection. Covers access token theft, refresh token replay, Primary Refresh Token (PRT) abuse, and pass-the
- [[implementing-passwordless-auth-with-microsoft-entra]] *(similar)* — Implements passwordless authentication using Microsoft Entra ID with FIDO2 security keys, Windows Hello for Business, Microsoft Authenticator passkeys, and certificate-based authentication to eliminate password-based attacks. Activates for requests involving passwordless deployment, FIDO2 passkey co
- [[performing-active-directory-forest-trust-attack]] *(similar)* — Enumerate and audit Active Directory forest trust relationships using impacket for SID filtering analysis, trust key extraction, cross-forest SID history abuse detection, and inter-realm Kerberos ticket assessment.
- [[performing-active-directory-vulnerability-assessment]] *(similar)* — Assess Active Directory security posture using PingCastle, BloodHound, and Purple Knight to identify misconfigurations, privilege escalation paths, and attack vectors.

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
