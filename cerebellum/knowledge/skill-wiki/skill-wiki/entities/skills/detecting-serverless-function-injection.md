---
title: detecting-serverless-function-injection
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [detecting-ai-model-prompt-injection-attacks, detecting-azure-service-principal-abuse, detecting-compromised-cloud-credentials, detecting-dll-sideloading-attacks, detecting-sql-injection-via-waf-logs, detecting-supply-chain-attacks-in-ci-cd, detecting-suspicious-powershell-execution, emulating-cloud-attacks-with-stratus-red-team, exploiting-template-injection-vulnerabilities]
confidence: medium
---

Detects and prevents code injection attacks targeting serverless functions (AWS Lambda, Azure Functions, Google Cloud Functions) through event source poisoning, malicious layer injection, runtime command execution, and IAM privilege escalation via function modification. The analyst combines static a

## Metadata

- **ID:** `detecting-serverless-function-injection`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-serverless-function-injection/SKILL.md`
- **Score:** 54.0
- **Edges:** 9

## Related Skills

- [[detecting-azure-service-principal-abuse]] *(similar)* — Detect and investigate Azure service principal abuse including privilege escalation, credential compromise, admin consent bypass, and unauthorized enumeration in Microsoft Entra ID environments.
- [[detecting-dll-sideloading-attacks]] *(similar)* — Detect DLL side-loading attacks where adversaries place malicious DLLs alongside legitimate applications to hijack execution flow for defense evasion.
- [[detecting-supply-chain-attacks-in-ci-cd]] *(similar)* — Scans GitHub Actions workflows and CI/CD pipeline configurations for supply chain attack vectors including unpinned actions, script injection via expressions, dependency confusion, and secrets exposure. Uses PyGithub and YAML parsing for automated audit. Use when hardening CI/CD pipelines or investi
- [[emulating-cloud-attacks-with-stratus-red-team]] *(similar)* — Detonate granular AWS, Azure, GCP, and Kubernetes attack techniques to validate detections with Stratus Red Team.
- [[exploiting-template-injection-vulnerabilities]] *(similar)* — Detecting and exploiting Server-Side Template Injection (SSTI) vulnerabilities across Jinja2, Twig, Freemarker, and other template engines to achieve remote code execution.
- [[detecting-ai-model-prompt-injection-attacks]] *(similar)* — Detects prompt injection attacks targeting LLM-based applications using a multi-layered defense combining regex pattern matching for known attack signatures, heuristic scoring for structural anomalies, and transformer-based classification with DeBERTa models. The detector analyzes user inputs before
- [[detecting-compromised-cloud-credentials]] *(similar)* — Detecting compromised cloud credentials across AWS, Azure, and GCP by analyzing anomalous API activity, impossible travel patterns, unauthorized resource provisioning, and credential abuse indicators using GuardDuty, Defender for Identity, and SCC Event Threat Detection.

- [[detecting-sql-injection-via-waf-logs]] *(similar)* — Analyze WAF (ModSecurity/AWS WAF/Cloudflare) logs to detect SQL injection attack campaigns. Parses ModSecurity audit logs and JSON WAF event logs to identify SQLi patterns (UNION SELECT, OR 1=1, SLEEP(), BENCHMARK()), tracks attack sources, correlates multi-stage injection attempts, and generates in
- [[detecting-suspicious-powershell-execution]] *(similar)* — Detect suspicious PowerShell execution patterns including encoded commands, download cradles, AMSI bypass attempts, and constrained language mode evasion.

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
