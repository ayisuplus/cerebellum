---
title: performing-paste-site-monitoring-for-credentials
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [auditing-tls-certificate-transparency-logs, deploying-honeytokens-and-canarytokens, detecting-aws-credential-exposure-with-trufflehog, detecting-shadow-api-endpoints, implementing-secret-scanning-with-gitleaks, implementing-secrets-scanning-in-ci-cd, performing-brand-monitoring-for-impersonation, performing-dark-web-monitoring-for-threats]
confidence: low
---

Monitor paste sites like Pastebin and GitHub Gists for leaked credentials, API keys, and sensitive data dumps using automated scraping and keyword matching to detect breaches early.

## Metadata

- **ID:** `performing-paste-site-monitoring-for-credentials`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/performing-paste-site-monitoring-for-credentials/SKILL.md`
- **Score:** 38.0
- **Edges:** 8

## Related Skills

- [[auditing-tls-certificate-transparency-logs]] *(similar)* — Monitors Certificate Transparency (CT) logs to detect unauthorized certificate issuance, discover subdomains via CT data, and alert on suspicious certificate activity for owned domains. Uses the crt.sh API and direct CT log querying based on RFC 6962 to build continuous monitoring pipelines that cat
- [[detecting-aws-credential-exposure-with-trufflehog]] *(similar)* — Detecting exposed AWS credentials in source code repositories, CI/CD pipelines, and configuration files using TruffleHog, git-secrets, and AWS-native detection mechanisms to prevent credential theft and unauthorized account access.

- [[detecting-shadow-api-endpoints]] *(similar)* — Discover and inventory shadow API endpoints that operate outside documented specifications using traffic analysis, code scanning, and API discovery platforms.
- [[implementing-secret-scanning-with-gitleaks]] *(similar)* — This skill covers implementing Gitleaks for detecting and preventing hardcoded secrets in git repositories. It addresses configuring pre-commit hooks, CI/CD pipeline integration, custom rule authoring for organization-specific secrets, baseline management for existing repositories, and remediation w
- [[implementing-secrets-scanning-in-ci-cd]] *(similar)* — Integrate gitleaks and trufflehog into CI/CD pipelines to detect leaked secrets before deployment
- [[deploying-honeytokens-and-canarytokens]] *(similar)* — Plant canarytokens and honey credentials and alert on breach.
- [[performing-brand-monitoring-for-impersonation]] *(similar)* — Monitor for brand impersonation attacks across domains, social media, mobile apps, and dark web channels to detect phishing campaigns, fake sites, and unauthorized brand usage targeting your organization.
- [[performing-dark-web-monitoring-for-threats]] *(similar)* — Dark web monitoring involves systematically scanning Tor hidden services, underground forums, paste sites, and dark web marketplaces to identify threats targeting an organization, including leaked cre

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
