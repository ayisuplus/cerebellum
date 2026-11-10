---
title: implementing-anti-ransomware-group-policy
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [configuring-ldap-security-hardening, configuring-network-segmentation-with-vlans, configuring-windows-defender-advanced-settings, implementing-application-whitelisting-with-applocker, implementing-ddos-mitigation-with-cloudflare, implementing-memory-protection-with-dep-aslr, implementing-passwordless-auth-with-microsoft-entra, investigating-ransomware-attack-artifacts]
confidence: medium
---

Configures Windows Group Policy Objects (GPO) to prevent ransomware execution and limit its spread. Implements AppLocker rules, Software Restriction Policies, Controlled Folder Access, attack surface reduction rules, and network protection settings. Activates for requests involving Windows GPO harde

## Metadata

- **ID:** `implementing-anti-ransomware-group-policy`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/implementing-anti-ransomware-group-policy/SKILL.md`
- **Score:** 50.0
- **Edges:** 8

## Related Skills

- [[implementing-application-whitelisting-with-applocker]] *(complement)* — Implements application whitelisting using Windows AppLocker to restrict unauthorized software execution on endpoints, reducing attack surface from malware, unauthorized tools, and shadow IT. Use when enforcing application control policies, meeting compliance requirements for software restriction, or
- [[configuring-ldap-security-hardening]] *(similar)* — Harden LDAP directory services against common attacks including credential harvesting, LDAP injection, anonymous binding, and channel binding bypass. Covers LDAPS enforcement, channel binding, LDAP si
- [[implementing-ddos-mitigation-with-cloudflare]] *(similar)* — Configure Cloudflare DDoS protection with managed rulesets, rate limiting, WAF rules, Bot Management, and origin protection to mitigate volumetric, protocol, and application-layer attacks.
- [[implementing-memory-protection-with-dep-aslr]] *(similar)* — Implements memory protection mechanisms including DEP (Data Execution Prevention), ASLR (Address Space Layout Randomization), CFG (Control Flow Guard), and other exploit mitigations to prevent memory corruption attacks. Use when hardening endpoints against buffer overflow exploits, ROP chains, and c
- [[investigating-ransomware-attack-artifacts]] *(similar)* — Identify, collect, and analyze ransomware attack artifacts to determine the variant, initial access vector, encryption scope, and recovery options.
- [[configuring-windows-defender-advanced-settings]] *(complement)* — Configures Microsoft Defender for Endpoint (MDE) advanced protection settings including attack surface reduction rules, controlled folder access, network protection, and exploit protection. Use when hardening Windows endpoints beyond default Defender settings, deploying enterprise-grade endpoint pro
- [[configuring-network-segmentation-with-vlans]] *(similar)* — Designs and implements VLAN-based network segmentation on managed switches to isolate network zones, enforce access control between segments, and reduce the attack surface by limiting lateral movement paths in enterprise network environments.

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
