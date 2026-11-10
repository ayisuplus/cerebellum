---
title: performing-http-parameter-pollution-attack
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [exploiting-http-request-smuggling, implementing-ddos-mitigation-with-cloudflare, performing-jwt-none-algorithm-attack, performing-second-order-sql-injection, performing-web-application-firewall-bypass, performing-web-cache-deception-attack, performing-web-cache-poisoning-attack]
confidence: medium
---

Execute HTTP Parameter Pollution attacks to bypass input validation, WAF rules, and security controls by injecting duplicate parameters that are processed differently by front-end and back-end systems.

## Metadata

- **ID:** `performing-http-parameter-pollution-attack`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/performing-http-parameter-pollution-attack/SKILL.md`
- **Score:** 46.0
- **Edges:** 7

## Related Skills

- [[performing-web-application-firewall-bypass]] *(complement)* — Bypass Web Application Firewall protections using encoding techniques, HTTP method manipulation, parameter pollution, and payload obfuscation to deliver SQL injection, XSS, and other attack payloads past WAF detection rules.
- [[exploiting-http-request-smuggling]] *(similar)* — Detecting and exploiting HTTP request smuggling vulnerabilities caused by Content-Length and Transfer-Encoding parsing discrepancies between front-end and back-end servers.
- [[performing-second-order-sql-injection]] *(similar)* — Detect and exploit second-order SQL injection vulnerabilities where malicious input is stored in a database and later executed in an unsafe SQL query during a different application operation.
- [[performing-web-cache-deception-attack]] *(similar)* — Execute web cache deception attacks by exploiting path normalization discrepancies between CDN caching layers and origin servers to cache and retrieve sensitive authenticated content.
- [[performing-web-cache-poisoning-attack]] *(similar)* — Exploiting web cache mechanisms to serve malicious content to other users by poisoning cached responses through unkeyed headers and parameters during authorized security tests.
- [[implementing-ddos-mitigation-with-cloudflare]] *(similar)* — Configure Cloudflare DDoS protection with managed rulesets, rate limiting, WAF rules, Bot Management, and origin protection to mitigate volumetric, protocol, and application-layer attacks.
- [[performing-jwt-none-algorithm-attack]] *(similar)* — Execute and test the JWT none algorithm attack to bypass signature verification by manipulating the alg header field in JSON Web Tokens.

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
