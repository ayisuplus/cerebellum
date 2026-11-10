---
title: performing-jwt-none-algorithm-attack
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [exploiting-jwt-algorithm-confusion-attack, performing-content-security-policy-bypass, performing-csrf-attack-simulation, performing-http-parameter-pollution-attack, performing-web-application-firewall-bypass, testing-jwt-token-security]
confidence: medium
---

Execute and test the JWT none algorithm attack to bypass signature verification by manipulating the alg header field in JSON Web Tokens.

## Metadata

- **ID:** `performing-jwt-none-algorithm-attack`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/performing-jwt-none-algorithm-attack/SKILL.md`
- **Score:** 50.0
- **Edges:** 6

## Related Skills

- [[performing-content-security-policy-bypass]] *(similar)* — Analyze and bypass Content Security Policy implementations to achieve cross-site scripting by exploiting misconfigurations, JSONP endpoints, unsafe directives, and policy injection techniques.
- [[performing-csrf-attack-simulation]] *(similar)* — Testing web applications for Cross-Site Request Forgery vulnerabilities by crafting forged requests that exploit authenticated user sessions during authorized security assessments.
- [[performing-http-parameter-pollution-attack]] *(similar)* — Execute HTTP Parameter Pollution attacks to bypass input validation, WAF rules, and security controls by injecting duplicate parameters that are processed differently by front-end and back-end systems.
- [[performing-web-application-firewall-bypass]] *(similar)* — Bypass Web Application Firewall protections using encoding techniques, HTTP method manipulation, parameter pollution, and payload obfuscation to deliver SQL injection, XSS, and other attack payloads past WAF detection rules.
- [[testing-jwt-token-security]] *(similar)* — Assessing JSON Web Token implementations for cryptographic weaknesses, algorithm confusion attacks, and authorization bypass vulnerabilities during security engagements.
- [[exploiting-jwt-algorithm-confusion-attack]] *(complement)* — Exploits JWT algorithm confusion vulnerabilities where the server's token verification library accepts the algorithm specified in the JWT header rather than enforcing a fixed algorithm. The tester manipulates the alg header to switch from RS256 to HS256 (using the RSA public key as the HMAC secret),

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
