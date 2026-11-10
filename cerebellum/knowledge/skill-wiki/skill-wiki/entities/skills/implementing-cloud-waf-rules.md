---
title: implementing-cloud-waf-rules
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [conducting-cloud-penetration-testing, detecting-sql-injection-via-waf-logs, emulating-cloud-attacks-with-stratus-red-team, implementing-api-rate-limiting-and-throttling, implementing-ddos-mitigation-with-cloudflare, implementing-runtime-application-self-protection, integrating-dast-with-owasp-zap-in-pipeline, performing-web-application-firewall-bypass]
confidence: medium
---

This skill covers deploying and tuning Web Application Firewall rules on AWS WAF, Azure WAF, and Cloudflare to protect cloud-hosted applications against OWASP Top 10 attacks. It details configuring managed rule sets, creating custom rules for business logic protection, implementing rate limiting, de

## Metadata

- **ID:** `implementing-cloud-waf-rules`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/implementing-cloud-waf-rules/SKILL.md`
- **Score:** 42.0
- **Edges:** 8

## Related Skills

- [[implementing-ddos-mitigation-with-cloudflare]] *(complement)* — Configure Cloudflare DDoS protection with managed rulesets, rate limiting, WAF rules, Bot Management, and origin protection to mitigate volumetric, protocol, and application-layer attacks.
- [[conducting-cloud-penetration-testing]] *(similar)* — This skill outlines methodologies for performing authorized penetration testing against AWS, Azure, and GCP cloud environments. It covers understanding the shared responsibility model for testing scope, leveraging cloud-specific attack tools like Pacu and ScoutSuite, exploiting IAM misconfigurations
- [[emulating-cloud-attacks-with-stratus-red-team]] *(similar)* — Detonate granular AWS, Azure, GCP, and Kubernetes attack techniques to validate detections with Stratus Red Team.
- [[implementing-runtime-application-self-protection]] *(similar)* — Deploy Runtime Application Self-Protection (RASP) agents to detect and block attacks from within application runtime, covering OpenRASP integration, attack pattern detection, and security policy configuration for Java and Python web applications.
- [[performing-web-application-firewall-bypass]] *(similar)* — Bypass Web Application Firewall protections using encoding techniques, HTTP method manipulation, parameter pollution, and payload obfuscation to deliver SQL injection, XSS, and other attack payloads past WAF detection rules.
- [[detecting-sql-injection-via-waf-logs]] *(similar)* — Analyze WAF (ModSecurity/AWS WAF/Cloudflare) logs to detect SQL injection attack campaigns. Parses ModSecurity audit logs and JSON WAF event logs to identify SQLi patterns (UNION SELECT, OR 1=1, SLEEP(), BENCHMARK()), tracks attack sources, correlates multi-stage injection attempts, and generates in
- [[implementing-api-rate-limiting-and-throttling]] *(similar)* — Implements API rate limiting and throttling controls using token bucket, sliding window, and fixed window algorithms to protect against brute force attacks, credential stuffing, resource exhaustion, and API abuse. The engineer configures per-user, per-IP, and per-endpoint rate limits using Redis-bac
- [[integrating-dast-with-owasp-zap-in-pipeline]] *(similar)* — This skill covers integrating OWASP ZAP (Zed Attack Proxy) for Dynamic Application Security Testing in CI/CD pipelines. It addresses configuring baseline, full, and API scans against running applications, interpreting ZAP findings, tuning scan policies, and establishing DAST quality gates in GitHub 

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
