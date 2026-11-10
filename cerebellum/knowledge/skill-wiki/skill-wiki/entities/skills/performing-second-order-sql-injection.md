---
title: performing-second-order-sql-injection
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [detecting-sql-injection-via-waf-logs, exploiting-api-injection-vulnerabilities, exploiting-mass-assignment-in-rest-apis, exploiting-nosql-injection-vulnerabilities, exploiting-sql-injection-with-sqlmap, exploiting-template-injection-vulnerabilities, performing-blind-ssrf-exploitation, performing-csrf-attack-simulation, performing-http-parameter-pollution-attack, performing-sqlite-database-forensics, performing-web-application-firewall-bypass, performing-web-cache-poisoning-attack]
confidence: medium
---

Detect and exploit second-order SQL injection vulnerabilities where malicious input is stored in a database and later executed in an unsafe SQL query during a different application operation.

## Metadata

- **ID:** `performing-second-order-sql-injection`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/performing-second-order-sql-injection/SKILL.md`
- **Score:** 52.0
- **Edges:** 12

## Related Skills

- [[exploiting-api-injection-vulnerabilities]] *(similar)* — Tests APIs for injection vulnerabilities including SQL injection, NoSQL injection, OS command injection, LDAP injection, and Server-Side Request Forgery (SSRF) through API parameters, headers, and request bodies. The tester crafts malicious payloads targeting different backend technologies and injec
- [[exploiting-mass-assignment-in-rest-apis]] *(similar)* — Discover and exploit mass assignment vulnerabilities in REST APIs to escalate privileges, modify restricted fields, and bypass authorization controls by injecting unexpected parameters in API requests.
- [[performing-csrf-attack-simulation]] *(similar)* — Testing web applications for Cross-Site Request Forgery vulnerabilities by crafting forged requests that exploit authenticated user sessions during authorized security assessments.
- [[performing-web-application-firewall-bypass]] *(similar)* — Bypass Web Application Firewall protections using encoding techniques, HTTP method manipulation, parameter pollution, and payload obfuscation to deliver SQL injection, XSS, and other attack payloads past WAF detection rules.
- [[performing-web-cache-poisoning-attack]] *(similar)* — Exploiting web cache mechanisms to serve malicious content to other users by poisoning cached responses through unkeyed headers and parameters during authorized security tests.
- [[exploiting-sql-injection-with-sqlmap]] *(complement)* — Detecting and exploiting SQL injection vulnerabilities using sqlmap to extract database contents during authorized penetration tests.
- [[detecting-sql-injection-via-waf-logs]] *(similar)* — Analyze WAF (ModSecurity/AWS WAF/Cloudflare) logs to detect SQL injection attack campaigns. Parses ModSecurity audit logs and JSON WAF event logs to identify SQLi patterns (UNION SELECT, OR 1=1, SLEEP(), BENCHMARK()), tracks attack sources, correlates multi-stage injection attempts, and generates in
- [[exploiting-nosql-injection-vulnerabilities]] *(similar)* — Detect and exploit NoSQL injection vulnerabilities in MongoDB, CouchDB, and other NoSQL databases to demonstrate authentication bypass, data extraction, and unauthorized access risks.
- [[exploiting-template-injection-vulnerabilities]] *(similar)* — Detecting and exploiting Server-Side Template Injection (SSTI) vulnerabilities across Jinja2, Twig, Freemarker, and other template engines to achieve remote code execution.
- [[performing-blind-ssrf-exploitation]] *(similar)* — Detect and exploit blind Server-Side Request Forgery vulnerabilities using out-of-band techniques, DNS interactions, and timing analysis to access internal services and cloud metadata endpoints.
- [[performing-http-parameter-pollution-attack]] *(similar)* — Execute HTTP Parameter Pollution attacks to bypass input validation, WAF rules, and security controls by injecting duplicate parameters that are processed differently by front-end and back-end systems.
- [[performing-sqlite-database-forensics]] *(similar)* — Perform forensic analysis of SQLite databases to recover deleted records from freelists and WAL files, decode encoded timestamps, and extract evidence from browser history, messaging apps, and mobile device databases.

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
