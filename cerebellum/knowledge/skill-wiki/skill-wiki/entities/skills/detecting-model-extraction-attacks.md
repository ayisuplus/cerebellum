---
title: detecting-model-extraction-attacks
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [detecting-ai-model-prompt-injection-attacks, detecting-api-enumeration-attacks, detecting-compromised-cloud-credentials, detecting-deepfake-audio-in-vishing-attacks, detecting-dll-sideloading-attacks, detecting-indirect-prompt-injection, detecting-insider-threat-behaviors, implementing-llm-guardrails-for-security, orchestrating-llm-attacks-with-pyrit, red-teaming-llms-with-garak, testing-prompt-injection-in-rag-pipelines]
confidence: medium
---

Detect model stealing, model inversion, and membership inference performed through inference-API abuse by monitoring query patterns, applying output perturbation, and red-teaming your own model's extractability.

## Metadata

- **ID:** `detecting-model-extraction-attacks`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-model-extraction-attacks/SKILL.md`
- **Score:** 43.0
- **Edges:** 11

## Related Skills

- [[detecting-compromised-cloud-credentials]] *(similar)* — Detecting compromised cloud credentials across AWS, Azure, and GCP by analyzing anomalous API activity, impossible travel patterns, unauthorized resource provisioning, and credential abuse indicators using GuardDuty, Defender for Identity, and SCC Event Threat Detection.

- [[detecting-dll-sideloading-attacks]] *(similar)* — Detect DLL side-loading attacks where adversaries place malicious DLLs alongside legitimate applications to hijack execution flow for defense evasion.
- [[implementing-llm-guardrails-for-security]] *(similar)* — Implements input and output validation guardrails for LLM-powered applications to prevent prompt injection, data leakage, toxic content generation, and hallucinated outputs. Builds a security validation pipeline using NVIDIA NeMo Guardrails Colang definitions, custom Python validators for PII detect
- [[red-teaming-llms-with-garak]] *(similar)* — Run NVIDIA garak probe suites against an LLM endpoint to test for jailbreaks, prompt injection, data leakage, and toxic generation, then interpret the hit-rate report for triage and reporting.
- [[testing-prompt-injection-in-rag-pipelines]] *(similar)* — Probe RAG applications for prompt injection via poisoned retrieved context and embedding manipulation.
- [[detecting-ai-model-prompt-injection-attacks]] *(similar)* — Detects prompt injection attacks targeting LLM-based applications using a multi-layered defense combining regex pattern matching for known attack signatures, heuristic scoring for structural anomalies, and transformer-based classification with DeBERTa models. The detector analyzes user inputs before
- [[detecting-api-enumeration-attacks]] *(similar)* — Detect and prevent API enumeration attacks including BOLA and IDOR exploitation by monitoring sequential identifier access patterns and authorization failures.
- [[detecting-deepfake-audio-in-vishing-attacks]] *(similar)* — Detects AI-generated deepfake audio used in voice phishing (vishing) attacks by extracting spectral features (MFCC, spectral centroid, spectral contrast, zero-crossing rate) and classifying samples with machine learning models. Supports batch analysis of audio files, generates confidence scores, and
- [[detecting-indirect-prompt-injection]] *(similar)* — Detect and defend against prompt injection hidden in documents, web pages, and images consumed by an agent.
- [[detecting-insider-threat-behaviors]] *(similar)* — Detect insider threat behavioral indicators including unusual data access, off-hours activity, mass file downloads, privilege abuse, and resignation-correlated data theft.
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
