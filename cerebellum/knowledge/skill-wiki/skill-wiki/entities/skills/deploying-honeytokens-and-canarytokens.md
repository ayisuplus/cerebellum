---
title: deploying-honeytokens-and-canarytokens
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [deploying-active-directory-honeytokens, deploying-ransomware-canary-files, detecting-aws-credential-exposure-with-trufflehog, detecting-network-anomalies-with-zeek, implementing-secrets-scanning-in-ci-cd, implementing-vulnerability-sla-breach-alerting, performing-paste-site-monitoring-for-credentials]
confidence: low
---

Plant canarytokens and honey credentials and alert on breach.

## Metadata

- **ID:** `deploying-honeytokens-and-canarytokens`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/deploying-honeytokens-and-canarytokens/SKILL.md`
- **Score:** 38.0
- **Edges:** 7

## Related Skills

- [[deploying-ransomware-canary-files]] *(similar)* — Deploys and monitors ransomware canary files across critical directories using Python's watchdog library for real-time filesystem event detection. Places strategically named decoy files that mimic high-value targets (financial records, credentials, database exports) in locations ransomware typically
- [[detecting-aws-credential-exposure-with-trufflehog]] *(similar)* — Detecting exposed AWS credentials in source code repositories, CI/CD pipelines, and configuration files using TruffleHog, git-secrets, and AWS-native detection mechanisms to prevent credential theft and unauthorized account access.

- [[detecting-network-anomalies-with-zeek]] *(similar)* — Deploys and configures Zeek (formerly Bro) network security monitor to passively analyze network traffic, generate structured logs, detect anomalous behavior, and create custom detection scripts for threat hunting and incident response.

- [[implementing-secrets-scanning-in-ci-cd]] *(similar)* — Integrate gitleaks and trufflehog into CI/CD pipelines to detect leaked secrets before deployment
- [[performing-paste-site-monitoring-for-credentials]] *(similar)* — Monitor paste sites like Pastebin and GitHub Gists for leaked credentials, API keys, and sensitive data dumps using automated scraping and keyword matching to detect breaches early.
- [[deploying-active-directory-honeytokens]] *(similar)* — Deploys deception-based honeytokens in Active Directory including fake privileged accounts with AdminCount=1, fake SPNs for Kerberoasting detection (honeyroasting), decoy GPOs with cpassword traps, and fake BloodHound paths. Monitors Windows Security Event IDs 4769, 4625, 4662, 5136 for honeytoken i
- [[implementing-vulnerability-sla-breach-alerting]] *(similar)* — Build automated alerting for vulnerability remediation SLA breaches with severity-based timelines, escalation workflows, and compliance reporting dashboards.

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
