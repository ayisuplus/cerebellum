---
title: detecting-api-enumeration-attacks
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-api-gateway-access-logs, analyzing-web-server-logs-for-intrusion, detecting-attacks-on-historian-servers, detecting-azure-service-principal-abuse, detecting-bluetooth-low-energy-attacks, detecting-broken-object-property-level-authorization, detecting-insider-threat-with-ueba, detecting-model-extraction-attacks, detecting-oauth-token-theft, exploiting-idor-vulnerabilities, performing-graphql-security-assessment]
confidence: low
---

Detect and prevent API enumeration attacks including BOLA and IDOR exploitation by monitoring sequential identifier access patterns and authorization failures.

## Metadata

- **ID:** `detecting-api-enumeration-attacks`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-api-enumeration-attacks/SKILL.md`
- **Score:** 37.0
- **Edges:** 11

## Related Skills

- [[detecting-azure-service-principal-abuse]] *(similar)* — Detect and investigate Azure service principal abuse including privilege escalation, credential compromise, admin consent bypass, and unauthorized enumeration in Microsoft Entra ID environments.
- [[detecting-broken-object-property-level-authorization]] *(similar)* — Detect and test for OWASP API3:2023 Broken Object Property Level Authorization vulnerabilities including excessive data exposure and mass assignment attacks.
- [[detecting-model-extraction-attacks]] *(similar)* — Detect model stealing, model inversion, and membership inference performed through inference-API abuse by monitoring query patterns, applying output perturbation, and red-teaming your own model's extractability.
- [[exploiting-idor-vulnerabilities]] *(similar)* — Identifying and exploiting Insecure Direct Object Reference vulnerabilities to access unauthorized resources by manipulating object identifiers in API requests and URLs.
- [[performing-graphql-security-assessment]] *(similar)* — Assessing GraphQL API endpoints for introspection leaks, injection attacks, authorization flaws, and denial-of-service vulnerabilities during authorized security tests.
- [[analyzing-api-gateway-access-logs]] *(similar)* — Parses API Gateway access logs (AWS API Gateway, Kong, Nginx) to detect BOLA/IDOR attacks, rate limit bypass, credential scanning, and injection attempts. Uses pandas for statistical analysis of request patterns and anomaly detection. Use when investigating API abuse or building API-specific threat 
- [[analyzing-web-server-logs-for-intrusion]] *(similar)* — Parse Apache and Nginx access logs to detect SQL injection attempts, local file inclusion, directory traversal, web scanner fingerprints, and brute-force patterns. Uses regex-based pattern matching against OWASP attack signatures, GeoIP enrichment for source attribution, and statistical anomaly dete
- [[detecting-attacks-on-historian-servers]] *(similar)* — Detect cyber attacks targeting OT historian servers (OSIsoft PI, Ignition, Wonderware) that sit at the IT/OT boundary and serve as pivot points for lateral movement between enterprise and control networks, including data manipulation, unauthorized queries, and exploitation of historian-specific vuln
- [[detecting-bluetooth-low-energy-attacks]] *(similar)* — Detects and analyzes Bluetooth Low Energy (BLE) security attacks including sniffing, replay attacks, GATT enumeration abuse, and Man-in-the-Middle interception. Uses Ubertooth One and nRF52840 sniffers for packet capture, the bleak Python library for GATT service enumeration, and crackle for BLE enc
- [[detecting-insider-threat-with-ueba]] *(similar)* — Implement User and Entity Behavior Analytics using Elasticsearch/OpenSearch to build behavioral baselines, calculate anomaly scores, perform peer group analysis, and detect insider threat indicators such as data exfiltration, privilege abuse, and unauthorized access patterns.
- [[detecting-oauth-token-theft]] *(similar)* — Detects and responds to OAuth token theft and replay attacks in cloud environments, focusing on Microsoft Entra ID (Azure AD) token protection, conditional access policies, and sign-in anomaly detection. Covers access token theft, refresh token replay, Primary Refresh Token (PRT) abuse, and pass-the

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
