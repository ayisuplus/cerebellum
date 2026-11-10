---
title: analyzing-web-server-logs-for-intrusion
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-api-gateway-access-logs, analyzing-pdf-malware-with-pdfid, detecting-ai-model-prompt-injection-attacks, detecting-api-enumeration-attacks, detecting-insider-threat-with-ueba, detecting-sql-injection-via-waf-logs, performing-web-application-firewall-bypass]
confidence: low
---

Parse Apache and Nginx access logs to detect SQL injection attempts, local file inclusion, directory traversal, web scanner fingerprints, and brute-force patterns. Uses regex-based pattern matching against OWASP attack signatures, GeoIP enrichment for source attribution, and statistical anomaly dete

## Metadata

- **ID:** `analyzing-web-server-logs-for-intrusion`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/analyzing-web-server-logs-for-intrusion/SKILL.md`
- **Score:** 38.0
- **Edges:** 7

## Related Skills

- [[detecting-sql-injection-via-waf-logs]] *(complement)* — Analyze WAF (ModSecurity/AWS WAF/Cloudflare) logs to detect SQL injection attack campaigns. Parses ModSecurity audit logs and JSON WAF event logs to identify SQLi patterns (UNION SELECT, OR 1=1, SLEEP(), BENCHMARK()), tracks attack sources, correlates multi-stage injection attempts, and generates in
- [[detecting-ai-model-prompt-injection-attacks]] *(similar)* — Detects prompt injection attacks targeting LLM-based applications using a multi-layered defense combining regex pattern matching for known attack signatures, heuristic scoring for structural anomalies, and transformer-based classification with DeBERTa models. The detector analyzes user inputs before
- [[detecting-api-enumeration-attacks]] *(similar)* — Detect and prevent API enumeration attacks including BOLA and IDOR exploitation by monitoring sequential identifier access patterns and authorization failures.
- [[detecting-insider-threat-with-ueba]] *(similar)* — Implement User and Entity Behavior Analytics using Elasticsearch/OpenSearch to build behavioral baselines, calculate anomaly scores, perform peer group analysis, and detect insider threat indicators such as data exfiltration, privilege abuse, and unauthorized access patterns.
- [[performing-web-application-firewall-bypass]] *(similar)* — Bypass Web Application Firewall protections using encoding techniques, HTTP method manipulation, parameter pollution, and payload obfuscation to deliver SQL injection, XSS, and other attack payloads past WAF detection rules.
- [[analyzing-api-gateway-access-logs]] *(complement)* — Parses API Gateway access logs (AWS API Gateway, Kong, Nginx) to detect BOLA/IDOR attacks, rate limit bypass, credential scanning, and injection attempts. Uses pandas for statistical analysis of request patterns and anomaly detection. Use when investigating API abuse or building API-specific threat 
- [[analyzing-pdf-malware-with-pdfid]] *(similar)* — Analyzes malicious PDF files using PDFiD, pdf-parser, and peepdf to identify embedded JavaScript, shellcode, exploits, and suspicious objects without opening the document. Determines the attack vector and extracts embedded payloads for further analysis. Activates for requests involving PDF malware a

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
