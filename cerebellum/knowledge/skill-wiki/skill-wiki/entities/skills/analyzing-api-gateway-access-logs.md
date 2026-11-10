---
title: analyzing-api-gateway-access-logs
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-pdf-malware-with-pdfid, analyzing-web-server-logs-for-intrusion, detecting-api-enumeration-attacks, detecting-compromised-cloud-credentials, detecting-sql-injection-via-waf-logs]
confidence: low
---

Parses API Gateway access logs (AWS API Gateway, Kong, Nginx) to detect BOLA/IDOR attacks, rate limit bypass, credential scanning, and injection attempts. Uses pandas for statistical analysis of request patterns and anomaly detection. Use when investigating API abuse or building API-specific threat

## Metadata

- **ID:** `analyzing-api-gateway-access-logs`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/analyzing-api-gateway-access-logs/SKILL.md`
- **Score:** 30.0
- **Edges:** 5

## Related Skills

- [[analyzing-web-server-logs-for-intrusion]] *(complement)* — Parse Apache and Nginx access logs to detect SQL injection attempts, local file inclusion, directory traversal, web scanner fingerprints, and brute-force patterns. Uses regex-based pattern matching against OWASP attack signatures, GeoIP enrichment for source attribution, and statistical anomaly dete
- [[analyzing-pdf-malware-with-pdfid]] *(similar)* — Analyzes malicious PDF files using PDFiD, pdf-parser, and peepdf to identify embedded JavaScript, shellcode, exploits, and suspicious objects without opening the document. Determines the attack vector and extracts embedded payloads for further analysis. Activates for requests involving PDF malware a
- [[detecting-api-enumeration-attacks]] *(similar)* — Detect and prevent API enumeration attacks including BOLA and IDOR exploitation by monitoring sequential identifier access patterns and authorization failures.
- [[detecting-compromised-cloud-credentials]] *(similar)* — Detecting compromised cloud credentials across AWS, Azure, and GCP by analyzing anomalous API activity, impossible travel patterns, unauthorized resource provisioning, and credential abuse indicators using GuardDuty, Defender for Identity, and SCC Event Threat Detection.

- [[detecting-sql-injection-via-waf-logs]] *(similar)* — Analyze WAF (ModSecurity/AWS WAF/Cloudflare) logs to detect SQL injection attack campaigns. Parses ModSecurity audit logs and JSON WAF event logs to identify SQLi patterns (UNION SELECT, OR 1=1, SLEEP(), BENCHMARK()), tracks attack sources, correlates multi-stage injection attempts, and generates in

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
