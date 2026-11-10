---
title: detecting-supply-chain-attacks-in-ci-cd
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [detecting-ai-model-prompt-injection-attacks, detecting-azure-service-principal-abuse, detecting-serverless-function-injection, integrating-dast-with-owasp-zap-in-pipeline, performing-supply-chain-attack-simulation, securing-github-actions-workflows]
confidence: low
---

Scans GitHub Actions workflows and CI/CD pipeline configurations for supply chain attack vectors including unpinned actions, script injection via expressions, dependency confusion, and secrets exposure. Uses PyGithub and YAML parsing for automated audit. Use when hardening CI/CD pipelines or investi

## Metadata

- **ID:** `detecting-supply-chain-attacks-in-ci-cd`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-supply-chain-attacks-in-ci-cd/SKILL.md`
- **Score:** 30.0
- **Edges:** 6

## Related Skills

- [[securing-github-actions-workflows]] *(complement)* — This skill covers hardening GitHub Actions workflows against supply chain attacks, credential theft, and privilege escalation. It addresses pinning actions to SHA digests, minimizing GITHUB_TOKEN permissions, protecting secrets from exfiltration, preventing script injection in workflow expressions, 
- [[detecting-ai-model-prompt-injection-attacks]] *(similar)* — Detects prompt injection attacks targeting LLM-based applications using a multi-layered defense combining regex pattern matching for known attack signatures, heuristic scoring for structural anomalies, and transformer-based classification with DeBERTa models. The detector analyzes user inputs before
- [[detecting-azure-service-principal-abuse]] *(similar)* — Detect and investigate Azure service principal abuse including privilege escalation, credential compromise, admin consent bypass, and unauthorized enumeration in Microsoft Entra ID environments.
- [[integrating-dast-with-owasp-zap-in-pipeline]] *(similar)* — This skill covers integrating OWASP ZAP (Zed Attack Proxy) for Dynamic Application Security Testing in CI/CD pipelines. It addresses configuring baseline, full, and API scans against running applications, interpreting ZAP findings, tuning scan policies, and establishing DAST quality gates in GitHub 
- [[performing-supply-chain-attack-simulation]] *(similar)* — Simulate and detect software supply chain attacks including typosquatting detection via Levenshtein distance, dependency confusion testing against private registries, package hash verification with pip, and known vulnerability scanning with pip-audit.
- [[detecting-serverless-function-injection]] *(similar)* — Detects and prevents code injection attacks targeting serverless functions (AWS Lambda, Azure Functions, Google Cloud Functions) through event source poisoning, malicious layer injection, runtime command execution, and IAM privilege escalation via function modification. The analyst combines static a

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
