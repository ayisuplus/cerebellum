---
title: orchestrating-llm-attacks-with-pyrit
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [continuous-llm-red-teaming-with-promptfoo, detecting-ai-model-prompt-injection-attacks, detecting-indirect-prompt-injection, detecting-model-extraction-attacks, implementing-llm-guardrails-for-security, red-teaming-llms-with-garak, testing-prompt-injection-in-rag-pipelines]
confidence: medium
---

Build multi-turn, Crescendo, and Tree-of-Attacks-with-Pruning (TAP) automated attack chains against conversational LLM agents using Microsoft PyRIT, with adversarial chat and scorer feedback loops.

## Metadata

- **ID:** `orchestrating-llm-attacks-with-pyrit`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/orchestrating-llm-attacks-with-pyrit/SKILL.md`
- **Score:** 47.0
- **Edges:** 7

## Related Skills

- [[detecting-ai-model-prompt-injection-attacks]] *(similar)* — Detects prompt injection attacks targeting LLM-based applications using a multi-layered defense combining regex pattern matching for known attack signatures, heuristic scoring for structural anomalies, and transformer-based classification with DeBERTa models. The detector analyzes user inputs before
- [[detecting-indirect-prompt-injection]] *(similar)* — Detect and defend against prompt injection hidden in documents, web pages, and images consumed by an agent.
- [[detecting-model-extraction-attacks]] *(similar)* — Detect model stealing, model inversion, and membership inference performed through inference-API abuse by monitoring query patterns, applying output perturbation, and red-teaming your own model's extractability.
- [[red-teaming-llms-with-garak]] *(similar)* — Run NVIDIA garak probe suites against an LLM endpoint to test for jailbreaks, prompt injection, data leakage, and toxic generation, then interpret the hit-rate report for triage and reporting.
- [[testing-prompt-injection-in-rag-pipelines]] *(similar)* — Probe RAG applications for prompt injection via poisoned retrieved context and embedding manipulation.
- [[continuous-llm-red-teaming-with-promptfoo]] *(similar)* — Wire Promptfoo and DeepTeam into CI/CD for automated regression red-teaming of LLM apps against OWASP LLM Top 10 and OWASP Agentic presets, failing the build when jailbreak or injection vulnerabilities regress.
- [[implementing-llm-guardrails-for-security]] *(similar)* — Implements input and output validation guardrails for LLM-powered applications to prevent prompt injection, data leakage, toxic content generation, and hallucinated outputs. Builds a security validation pipeline using NVIDIA NeMo Guardrails Colang definitions, custom Python validators for PII detect

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
