---
title: performing-web-cache-poisoning-attack
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [exploiting-http-request-smuggling, performing-clickjacking-attack-test, performing-content-security-policy-bypass, performing-csrf-attack-simulation, performing-http-parameter-pollution-attack, performing-second-order-sql-injection, performing-soap-web-service-security-testing, performing-ssl-stripping-attack, performing-web-application-firewall-bypass, performing-web-cache-deception-attack, testing-cors-misconfiguration, testing-for-host-header-injection, testing-for-open-redirect-vulnerabilities, testing-for-xss-vulnerabilities-with-burpsuite]
confidence: medium
---

Exploiting web cache mechanisms to serve malicious content to other users by poisoning cached responses through unkeyed headers and parameters during authorized security tests.

## Metadata

- **ID:** `performing-web-cache-poisoning-attack`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/performing-web-cache-poisoning-attack/SKILL.md`
- **Score:** 50.0
- **Edges:** 14

## Related Skills

- [[testing-for-host-header-injection]] *(complement)* — Test web applications for HTTP Host header injection vulnerabilities to identify password reset poisoning, web cache poisoning, SSRF, and virtual host routing manipulation risks.
- [[performing-content-security-policy-bypass]] *(similar)* — Analyze and bypass Content Security Policy implementations to achieve cross-site scripting by exploiting misconfigurations, JSONP endpoints, unsafe directives, and policy injection techniques.
- [[performing-soap-web-service-security-testing]] *(similar)* — Perform security testing of SOAP web services by analyzing WSDL definitions and testing for XML injection, XXE, WS-Security bypass, and SOAPAction spoofing.
- [[testing-cors-misconfiguration]] *(similar)* — Identifying and exploiting Cross-Origin Resource Sharing misconfigurations that allow unauthorized cross-domain data access and credential theft during security assessments.
- [[testing-for-open-redirect-vulnerabilities]] *(similar)* — Identify and test open redirect vulnerabilities in web applications by analyzing URL redirection parameters, bypass techniques, and exploitation chains for phishing and token theft.
- [[performing-csrf-attack-simulation]] *(complement)* — Testing web applications for Cross-Site Request Forgery vulnerabilities by crafting forged requests that exploit authenticated user sessions during authorized security assessments.
- [[performing-web-cache-deception-attack]] *(complement)* — Execute web cache deception attacks by exploiting path normalization discrepancies between CDN caching layers and origin servers to cache and retrieve sensitive authenticated content.
- [[exploiting-http-request-smuggling]] *(similar)* — Detecting and exploiting HTTP request smuggling vulnerabilities caused by Content-Length and Transfer-Encoding parsing discrepancies between front-end and back-end servers.
- [[performing-clickjacking-attack-test]] *(similar)* — Testing web applications for clickjacking vulnerabilities by assessing frame embedding controls and crafting proof-of-concept overlay attacks during authorized security assessments.
- [[performing-http-parameter-pollution-attack]] *(similar)* — Execute HTTP Parameter Pollution attacks to bypass input validation, WAF rules, and security controls by injecting duplicate parameters that are processed differently by front-end and back-end systems.
- [[performing-second-order-sql-injection]] *(similar)* — Detect and exploit second-order SQL injection vulnerabilities where malicious input is stored in a database and later executed in an unsafe SQL query during a different application operation.
- [[performing-ssl-stripping-attack]] *(similar)* — Simulates SSL stripping attacks using sslstrip, Bettercap, and mitmproxy in authorized environments to test HSTS enforcement, certificate validation, and HTTPS upgrade mechanisms that protect users from downgrade attacks on encrypted connections.

- [[performing-web-application-firewall-bypass]] *(similar)* — Bypass Web Application Firewall protections using encoding techniques, HTTP method manipulation, parameter pollution, and payload obfuscation to deliver SQL injection, XSS, and other attack payloads past WAF detection rules.
- [[testing-for-xss-vulnerabilities-with-burpsuite]] *(similar)* — Identifying and validating cross-site scripting vulnerabilities using Burp Suite's scanner, intruder, and repeater tools during authorized security assessments.

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
