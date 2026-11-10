---
title: detecting-indirect-prompt-injection
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [continuous-llm-red-teaming-with-promptfoo, detecting-ai-model-prompt-injection-attacks, detecting-model-extraction-attacks, detecting-qr-code-phishing-with-email-security, implementing-llm-guardrails-for-security, orchestrating-llm-attacks-with-pyrit, red-teaming-llms-with-garak, testing-prompt-injection-in-rag-pipelines]
confidence: low
---

Detect and defend against prompt injection hidden in documents, web pages, and images consumed by an agent.

## Metadata

- **ID:** `detecting-indirect-prompt-injection`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-indirect-prompt-injection/SKILL.md`
- **Score:** 35.0
- **Edges:** 8

## Related Skills

- [[testing-prompt-injection-in-rag-pipelines]] *(complement)* — Probe RAG applications for prompt injection via poisoned retrieved context and embedding manipulation.
- [[detecting-model-extraction-attacks]] *(similar)* — Detect model stealing, model inversion, and membership inference performed through inference-API abuse by monitoring query patterns, applying output perturbation, and red-teaming your own model's extractability.
- [[detecting-qr-code-phishing-with-email-security]] *(similar)* — Detect and prevent QR code phishing (quishing) attacks that bypass traditional email security by embedding malicious URLs in QR code images within emails.
- [[implementing-llm-guardrails-for-security]] *(similar)* — Implements input and output validation guardrails for LLM-powered applications to prevent prompt injection, data leakage, toxic content generation, and hallucinated outputs. Builds a security validation pipeline using NVIDIA NeMo Guardrails Colang definitions, custom Python validators for PII detect
- [[red-teaming-llms-with-garak]] *(similar)* — Run NVIDIA garak probe suites against an LLM endpoint to test for jailbreaks, prompt injection, data leakage, and toxic generation, then interpret the hit-rate report for triage and reporting.
- [[detecting-ai-model-prompt-injection-attacks]] *(complement)* — Detects prompt injection attacks targeting LLM-based applications using a multi-layered defense combining regex pattern matching for known attack signatures, heuristic scoring for structural anomalies, and transformer-based classification with DeBERTa models. The detector analyzes user inputs before
- [[continuous-llm-red-teaming-with-promptfoo]] *(similar)* — Wire Promptfoo and DeepTeam into CI/CD for automated regression red-teaming of LLM apps against OWASP LLM Top 10 and OWASP Agentic presets, failing the build when jailbreak or injection vulnerabilities regress.
- [[orchestrating-llm-attacks-with-pyrit]] *(similar)* — Build multi-turn, Crescendo, and Tree-of-Attacks-with-Pruning (TAP) automated attack chains against conversational LLM agents using Microsoft PyRIT, with adversarial chat and scorer feedback loops.

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
