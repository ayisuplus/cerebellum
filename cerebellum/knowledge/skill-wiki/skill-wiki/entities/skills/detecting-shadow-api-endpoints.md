---
title: detecting-shadow-api-endpoints
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [auditing-tls-certificate-transparency-logs, conducting-api-security-testing, detecting-aws-cloudtrail-anomalies, detecting-aws-credential-exposure-with-trufflehog, detecting-data-and-model-poisoning, detecting-mobile-malware-behavior, detecting-shadow-it-cloud-usage, hunting-for-command-and-control-beaconing, performing-paste-site-monitoring-for-credentials, testing-api-authentication-weaknesses]
confidence: low
---

Discover and inventory shadow API endpoints that operate outside documented specifications using traffic analysis, code scanning, and API discovery platforms.

## Metadata

- **ID:** `detecting-shadow-api-endpoints`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-shadow-api-endpoints/SKILL.md`
- **Score:** 39.0
- **Edges:** 10

## Related Skills

- [[detecting-aws-cloudtrail-anomalies]] *(similar)* — Detect unusual API call patterns in AWS CloudTrail logs using boto3, statistical baselining, and behavioral analysis to identify credential compromise, privilege escalation, and unauthorized resource access.
- [[detecting-aws-credential-exposure-with-trufflehog]] *(similar)* — Detecting exposed AWS credentials in source code repositories, CI/CD pipelines, and configuration files using TruffleHog, git-secrets, and AWS-native detection mechanisms to prevent credential theft and unauthorized account access.

- [[detecting-mobile-malware-behavior]] *(similar)* — Detects and analyzes malicious behavior in mobile applications through behavioral analysis, permission abuse detection, network traffic monitoring, and dynamic instrumentation. Use when analyzing suspicious mobile applications for data exfiltration, command-and-control communication, credential stea
- [[detecting-shadow-it-cloud-usage]] *(similar)* — Detect unauthorized SaaS and cloud service usage (shadow IT) by analyzing proxy logs, DNS query logs, and netflow data using Python pandas for traffic pattern analysis and domain classification.
- [[hunting-for-command-and-control-beaconing]] *(similar)* — Detect C2 beaconing patterns in network traffic using frequency analysis, jitter detection, and domain reputation to identify compromised endpoints communicating with adversary infrastructure.
- [[auditing-tls-certificate-transparency-logs]] *(similar)* — Monitors Certificate Transparency (CT) logs to detect unauthorized certificate issuance, discover subdomains via CT data, and alert on suspicious certificate activity for owned domains. Uses the crt.sh API and direct CT log querying based on RFC 6962 to build continuous monitoring pipelines that cat
- [[conducting-api-security-testing]] *(similar)* — Conducts security testing of REST, GraphQL, and gRPC APIs to identify vulnerabilities in authentication, authorization, rate limiting, input validation, and business logic. The tester uses the OWASP API Security Top 10 as the testing framework, combining Burp Suite interception with Postman collecti
- [[detecting-data-and-model-poisoning]] *(similar)* — Identify poisoned training data and backdoored models across the ML pipeline.
- [[performing-paste-site-monitoring-for-credentials]] *(similar)* — Monitor paste sites like Pastebin and GitHub Gists for leaked credentials, API keys, and sensitive data dumps using automated scraping and keyword matching to detect breaches early.
- [[testing-api-authentication-weaknesses]] *(similar)* — Tests API authentication mechanisms for weaknesses including broken token validation, missing authentication on endpoints, weak password policies, credential stuffing susceptibility, token leakage in URLs or logs, and session management flaws. The tester evaluates JWT implementation, API key handlin

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
