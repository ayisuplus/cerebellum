---
title: performing-csrf-attack-simulation
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [bypassing-authentication-with-forced-browsing, executing-phishing-simulation-campaign, exploiting-race-condition-vulnerabilities, performing-adversary-in-the-middle-phishing-detection, performing-api-security-testing-with-postman, performing-arp-spoofing-attack-simulation, performing-bandwidth-throttling-attack-simulation, performing-blind-ssrf-exploitation, performing-clickjacking-attack-test, performing-content-security-policy-bypass, performing-graphql-depth-limit-attack, performing-graphql-security-assessment, performing-initial-access-with-evilginx3, performing-jwt-none-algorithm-attack, performing-packet-injection-attack, performing-red-team-phishing-with-gophish, performing-red-team-with-covenant, performing-s7comm-protocol-security-analysis, performing-second-order-sql-injection, performing-soap-web-service-security-testing, performing-ssl-stripping-attack, performing-supply-chain-attack-simulation, performing-vlan-hopping-attack, performing-web-application-firewall-bypass, performing-web-application-penetration-test, performing-web-cache-deception-attack, performing-web-cache-poisoning-attack, testing-cors-misconfiguration, testing-for-host-header-injection, testing-for-open-redirect-vulnerabilities, testing-for-xml-injection-vulnerabilities, testing-for-xss-vulnerabilities, testing-for-xss-vulnerabilities-with-burpsuite, testing-jwt-token-security, testing-oauth2-implementation-flaws, testing-websocket-api-security]
confidence: medium
---

Testing web applications for Cross-Site Request Forgery vulnerabilities by crafting forged requests that exploit authenticated user sessions during authorized security assessments.

## Metadata

- **ID:** `performing-csrf-attack-simulation`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/performing-csrf-attack-simulation/SKILL.md`
- **Score:** 50.0
- **Edges:** 36

## Related Skills

- [[performing-web-cache-poisoning-attack]] *(complement)* — Exploiting web cache mechanisms to serve malicious content to other users by poisoning cached responses through unkeyed headers and parameters during authorized security tests.
- [[testing-cors-misconfiguration]] *(complement)* — Identifying and exploiting Cross-Origin Resource Sharing misconfigurations that allow unauthorized cross-domain data access and credential theft during security assessments.
- [[testing-for-xss-vulnerabilities]] *(complement)* — Tests web applications for Cross-Site Scripting (XSS) vulnerabilities by injecting JavaScript payloads into reflected, stored, and DOM-based contexts to demonstrate client-side code execution, session hijacking, and user impersonation. The tester identifies all injection points and output contexts, 
- [[performing-soap-web-service-security-testing]] *(similar)* — Perform security testing of SOAP web services by analyzing WSDL definitions and testing for XML injection, XXE, WS-Security bypass, and SOAPAction spoofing.
- [[performing-web-cache-deception-attack]] *(similar)* — Execute web cache deception attacks by exploiting path normalization discrepancies between CDN caching layers and origin servers to cache and retrieve sensitive authenticated content.
- [[performing-clickjacking-attack-test]] *(complement)* — Testing web applications for clickjacking vulnerabilities by assessing frame embedding controls and crafting proof-of-concept overlay attacks during authorized security assessments.
- [[bypassing-authentication-with-forced-browsing]] *(similar)* — Discovering and accessing unprotected pages, APIs, and administrative interfaces by enumerating URLs and bypassing authentication controls during authorized security assessments.
- [[executing-phishing-simulation-campaign]] *(similar)* — Executes authorized phishing simulation campaigns to assess an organization's susceptibility to email-based social engineering attacks. The tester designs realistic phishing scenarios, builds credential harvesting infrastructure, sends targeted phishing emails, and tracks open rates, click-through r
- [[exploiting-race-condition-vulnerabilities]] *(similar)* — Detect and exploit race condition vulnerabilities in web applications using Turbo Intruder's single-packet attack technique to bypass rate limits, duplicate transactions, and exploit time-of-check-to-time-of-use flaws.
- [[performing-adversary-in-the-middle-phishing-detection]] *(similar)* — Detect and respond to Adversary-in-the-Middle (AiTM) phishing attacks that use reverse proxy kits like EvilProxy, Evilginx, and Tycoon 2FA to bypass MFA and steal session tokens.
- [[performing-api-security-testing-with-postman]] *(similar)* — Uses Postman to perform structured API security testing by building collections that test for OWASP API Security Top 10 vulnerabilities including authentication bypass, authorization flaws, injection, and data exposure. The tester creates environments with multiple user roles, writes test scripts fo
- [[performing-arp-spoofing-attack-simulation]] *(similar)* — Simulates ARP spoofing attacks in authorized lab or pentest environments using arpspoof, Ettercap, and Scapy to demonstrate man-in-the-middle risks, test network detection capabilities, and validate ARP inspection countermeasures.

- [[performing-bandwidth-throttling-attack-simulation]] *(similar)* — Simulates bandwidth throttling and network degradation attacks using tc, iperf3, and Scapy in authorized environments to test quality-of-service controls, application resilience, and network monitoring detection of traffic manipulation attacks.

- [[performing-blind-ssrf-exploitation]] *(similar)* — Detect and exploit blind Server-Side Request Forgery vulnerabilities using out-of-band techniques, DNS interactions, and timing analysis to access internal services and cloud metadata endpoints.
- [[performing-content-security-policy-bypass]] *(similar)* — Analyze and bypass Content Security Policy implementations to achieve cross-site scripting by exploiting misconfigurations, JSONP endpoints, unsafe directives, and policy injection techniques.
- [[performing-graphql-depth-limit-attack]] *(similar)* — Execute and test GraphQL depth limit attacks using deeply nested recursive queries to identify denial-of-service vulnerabilities in GraphQL APIs.
- [[performing-graphql-security-assessment]] *(similar)* — Assessing GraphQL API endpoints for introspection leaks, injection attacks, authorization flaws, and denial-of-service vulnerabilities during authorized security tests.
- [[performing-initial-access-with-evilginx3]] *(similar)* — Perform authorized initial access using EvilGinx3 adversary-in-the-middle phishing framework to capture session tokens and bypass multi-factor authentication during red team engagements.
- [[performing-jwt-none-algorithm-attack]] *(similar)* — Execute and test the JWT none algorithm attack to bypass signature verification by manipulating the alg header field in JSON Web Tokens.
- [[performing-packet-injection-attack]] *(similar)* — Crafts and injects custom network packets using Scapy, hping3, and Nemesis during authorized security assessments to test firewall rules, IDS detection, protocol handling, and network stack resilience against malformed and spoofed traffic.

- [[performing-red-team-phishing-with-gophish]] *(similar)* — Automate GoPhish phishing simulation campaigns using the Python gophish library. Creates email templates with tracking pixels, configures SMTP sending profiles, builds target groups from CSV, launches campaigns, and analyzes results including open rates, click rates, and credential submission statis
- [[performing-red-team-with-covenant]] *(similar)* — Conduct red team operations using the Covenant C2 framework for authorized adversary simulation, including listener setup, grunt deployment, task execution, and lateral movement tracking.
- [[performing-s7comm-protocol-security-analysis]] *(similar)* — Perform security analysis of Siemens S7comm and S7CommPlus protocols used by SIMATIC S7 PLCs to identify vulnerabilities including replay attacks, integrity bypass, unauthorized CPU stop commands, and program download manipulation exploiting weaknesses in S7-300, S7-400, S7-1200, and S7-1500 control
- [[performing-second-order-sql-injection]] *(similar)* — Detect and exploit second-order SQL injection vulnerabilities where malicious input is stored in a database and later executed in an unsafe SQL query during a different application operation.
- [[performing-ssl-stripping-attack]] *(similar)* — Simulates SSL stripping attacks using sslstrip, Bettercap, and mitmproxy in authorized environments to test HSTS enforcement, certificate validation, and HTTPS upgrade mechanisms that protect users from downgrade attacks on encrypted connections.

- [[performing-supply-chain-attack-simulation]] *(similar)* — Simulate and detect software supply chain attacks including typosquatting detection via Levenshtein distance, dependency confusion testing against private registries, package hash verification with pip, and known vulnerability scanning with pip-audit.
- [[performing-vlan-hopping-attack]] *(similar)* — Simulates VLAN hopping attacks using switch spoofing and double tagging techniques in authorized environments to test VLAN segmentation effectiveness and validate switch port security configurations against Layer 2 bypass attacks.

- [[performing-web-application-firewall-bypass]] *(similar)* — Bypass Web Application Firewall protections using encoding techniques, HTTP method manipulation, parameter pollution, and payload obfuscation to deliver SQL injection, XSS, and other attack payloads past WAF detection rules.
- [[performing-web-application-penetration-test]] *(similar)* — Performs systematic security testing of web applications following the OWASP Web Security Testing Guide (WSTG) methodology to identify vulnerabilities in authentication, authorization, input validation, session management, and business logic. The tester uses Burp Suite as the primary interception pr
- [[testing-for-host-header-injection]] *(similar)* — Test web applications for HTTP Host header injection vulnerabilities to identify password reset poisoning, web cache poisoning, SSRF, and virtual host routing manipulation risks.
- [[testing-for-open-redirect-vulnerabilities]] *(similar)* — Identify and test open redirect vulnerabilities in web applications by analyzing URL redirection parameters, bypass techniques, and exploitation chains for phishing and token theft.
- [[testing-for-xml-injection-vulnerabilities]] *(similar)* — Test web applications for XML injection vulnerabilities including XXE, XPath injection, and XML entity attacks to identify data exposure and server-side request forgery risks.
- [[testing-for-xss-vulnerabilities-with-burpsuite]] *(similar)* — Identifying and validating cross-site scripting vulnerabilities using Burp Suite's scanner, intruder, and repeater tools during authorized security assessments.
- [[testing-jwt-token-security]] *(similar)* — Assessing JSON Web Token implementations for cryptographic weaknesses, algorithm confusion attacks, and authorization bypass vulnerabilities during security engagements.
- [[testing-oauth2-implementation-flaws]] *(similar)* — Tests OAuth 2.0 and OpenID Connect implementations for security flaws including authorization code interception, redirect URI manipulation, CSRF in OAuth flows, token leakage, scope escalation, and PKCE bypass. The tester evaluates the authorization server, client application, and token handling for
- [[testing-websocket-api-security]] *(similar)* — Tests WebSocket API implementations for security vulnerabilities including missing authentication on WebSocket upgrade, Cross-Site WebSocket Hijacking (CSWSH), injection attacks through WebSocket messages, insufficient input validation, denial-of-service via message flooding, and information leakage

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
