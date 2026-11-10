---
title: detecting-sql-injection-via-waf-logs
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-api-gateway-access-logs, analyzing-web-server-logs-for-intrusion, detecting-serverless-function-injection, exploiting-sql-injection-with-sqlmap, implementing-cloud-waf-rules, performing-second-order-sql-injection, performing-web-application-firewall-bypass]
confidence: low
---

Analyze WAF (ModSecurity/AWS WAF/Cloudflare) logs to detect SQL injection attack campaigns. Parses ModSecurity audit logs and JSON WAF event logs to identify SQLi patterns (UNION SELECT, OR 1=1, SLEEP(), BENCHMARK()), tracks attack sources, correlates multi-stage injection attempts, and generates in

## Metadata

- **ID:** `detecting-sql-injection-via-waf-logs`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-sql-injection-via-waf-logs/SKILL.md`
- **Score:** 37.0
- **Edges:** 7

## Related Skills

- [[detecting-serverless-function-injection]] *(similar)* — Detects and prevents code injection attacks targeting serverless functions (AWS Lambda, Azure Functions, Google Cloud Functions) through event source poisoning, malicious layer injection, runtime command execution, and IAM privilege escalation via function modification. The analyst combines static a
- [[exploiting-sql-injection-with-sqlmap]] *(similar)* — Detecting and exploiting SQL injection vulnerabilities using sqlmap to extract database contents during authorized penetration tests.
- [[implementing-cloud-waf-rules]] *(similar)* — This skill covers deploying and tuning Web Application Firewall rules on AWS WAF, Azure WAF, and Cloudflare to protect cloud-hosted applications against OWASP Top 10 attacks. It details configuring managed rule sets, creating custom rules for business logic protection, implementing rate limiting, de
- [[performing-second-order-sql-injection]] *(similar)* — Detect and exploit second-order SQL injection vulnerabilities where malicious input is stored in a database and later executed in an unsafe SQL query during a different application operation.
- [[performing-web-application-firewall-bypass]] *(similar)* — Bypass Web Application Firewall protections using encoding techniques, HTTP method manipulation, parameter pollution, and payload obfuscation to deliver SQL injection, XSS, and other attack payloads past WAF detection rules.
- [[analyzing-web-server-logs-for-intrusion]] *(complement)* — Parse Apache and Nginx access logs to detect SQL injection attempts, local file inclusion, directory traversal, web scanner fingerprints, and brute-force patterns. Uses regex-based pattern matching against OWASP attack signatures, GeoIP enrichment for source attribution, and statistical anomaly dete
- [[analyzing-api-gateway-access-logs]] *(similar)* — Parses API Gateway access logs (AWS API Gateway, Kong, Nginx) to detect BOLA/IDOR attacks, rate limit bypass, credential scanning, and injection attempts. Uses pandas for statistical analysis of request patterns and anomaly detection. Use when investigating API abuse or building API-specific threat 

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
