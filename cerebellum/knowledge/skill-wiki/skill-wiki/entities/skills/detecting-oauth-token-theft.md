---
title: detecting-oauth-token-theft
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [attacking-oauth-with-device-code-phishing, auditing-entra-id-with-aadinternals, detecting-api-enumeration-attacks, detecting-azure-service-principal-abuse, detecting-compromised-cloud-credentials, exploiting-oauth-misconfiguration, hunting-saas-sso-token-abuse, implementing-passwordless-auth-with-microsoft-entra, performing-adversary-in-the-middle-phishing-detection]
confidence: medium
---

Detects and responds to OAuth token theft and replay attacks in cloud environments, focusing on Microsoft Entra ID (Azure AD) token protection, conditional access policies, and sign-in anomaly detection. Covers access token theft, refresh token replay, Primary Refresh Token (PRT) abuse, and pass-the

## Metadata

- **ID:** `detecting-oauth-token-theft`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-oauth-token-theft/SKILL.md`
- **Score:** 44.0
- **Edges:** 9

## Related Skills

- [[auditing-entra-id-with-aadinternals]] *(similar)* — Run Microsoft Entra ID tenant reconnaissance, token acquisition and manipulation, and federation backdoor testing with the AADInternals PowerShell toolkit to validate identity-attack resilience.
- [[detecting-api-enumeration-attacks]] *(similar)* — Detect and prevent API enumeration attacks including BOLA and IDOR exploitation by monitoring sequential identifier access patterns and authorization failures.
- [[exploiting-oauth-misconfiguration]] *(similar)* — Identifying and exploiting OAuth 2.0 and OpenID Connect misconfigurations including redirect URI manipulation, token leakage, and authorization code theft during security assessments.
- [[hunting-saas-sso-token-abuse]] *(similar)* — Detect SSO and OAuth token replay and SaaS lateral movement.
- [[performing-adversary-in-the-middle-phishing-detection]] *(similar)* — Detect and respond to Adversary-in-the-Middle (AiTM) phishing attacks that use reverse proxy kits like EvilProxy, Evilginx, and Tycoon 2FA to bypass MFA and steal session tokens.
- [[detecting-azure-service-principal-abuse]] *(complement)* — Detect and investigate Azure service principal abuse including privilege escalation, credential compromise, admin consent bypass, and unauthorized enumeration in Microsoft Entra ID environments.
- [[attacking-oauth-with-device-code-phishing]] *(similar)* — Run OAuth 2.0 device-code and illicit-consent phishing against Microsoft Entra ID to steal access and refresh tokens, bypass MFA, and pivot across Microsoft 365 services.
- [[detecting-compromised-cloud-credentials]] *(similar)* — Detecting compromised cloud credentials across AWS, Azure, and GCP by analyzing anomalous API activity, impossible travel patterns, unauthorized resource provisioning, and credential abuse indicators using GuardDuty, Defender for Identity, and SCC Event Threat Detection.

- [[implementing-passwordless-auth-with-microsoft-entra]] *(similar)* — Implements passwordless authentication using Microsoft Entra ID with FIDO2 security keys, Windows Hello for Business, Microsoft Authenticator passkeys, and certificate-based authentication to eliminate password-based attacks. Activates for requests involving passwordless deployment, FIDO2 passkey co

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
