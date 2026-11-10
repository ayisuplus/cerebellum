---
title: building-ioc-defanging-and-sharing-pipeline
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-indicators-of-compromise, automating-ioc-enrichment, building-automated-malware-submission-pipeline, building-ioc-enrichment-pipeline-with-opencti, building-threat-intelligence-enrichment-in-splunk, building-threat-intelligence-feed-integration, collecting-indicators-of-compromise, collecting-threat-intelligence-with-misp, implementing-security-information-sharing-with-stix2, implementing-stix-taxii-feed-integration, performing-malware-ioc-extraction, processing-stix-taxii-feeds]
confidence: medium
---

Build an automated pipeline to defang indicators of compromise (URLs, IPs, domains, emails) for safe sharing and distribute them in STIX format through TAXII feeds and threat intelligence platforms.

## Metadata

- **ID:** `building-ioc-defanging-and-sharing-pipeline`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/building-ioc-defanging-and-sharing-pipeline/SKILL.md`
- **Score:** 45.0
- **Edges:** 12

## Related Skills

- [[building-ioc-enrichment-pipeline-with-opencti]] *(complement)* — OpenCTI is an open-source platform for managing cyber threat intelligence knowledge, built on STIX 2.1 as its native data model. This skill covers building an automated IOC enrichment pipeline using O
- [[building-threat-intelligence-feed-integration]] *(complement)* — Builds automated threat intelligence feed integration pipelines connecting STIX/TAXII feeds, open-source threat intel, and commercial TI platforms into SIEM and security tools for real-time IOC matching and alerting. Use when SOC teams need to operationalize threat intelligence by automating feed in
- [[analyzing-indicators-of-compromise]] *(similar)* — Analyzes indicators of compromise (IOCs) including IP addresses, domains, file hashes, URLs, and email artifacts to determine maliciousness confidence, campaign attribution, and blocking priority. Use when triaging IOCs from phishing emails, security alerts, or external threat feeds; enriching raw I
- [[collecting-indicators-of-compromise]] *(similar)* — Systematically collects, categorizes, and distributes indicators of compromise (IOCs) during and after security incidents to enable detection, blocking, and threat intelligence sharing. Covers network, host, email, and behavioral indicators using STIX/TAXII formats and threat intelligence platforms.
- [[processing-stix-taxii-feeds]] *(similar)* — Processes STIX 2.1 threat intelligence bundles delivered via TAXII 2.1 servers, normalizing objects into platform-native schemas and routing them to appropriate consuming systems. Use when onboarding new TAXII collection endpoints, automating bi-directional intelligence sharing with ISACs, or buildi
- [[automating-ioc-enrichment]] *(complement)* — Automates the enrichment of raw indicators of compromise with multi-source threat intelligence context using SOAR platforms, Python pipelines, or TIP playbooks to reduce analyst triage time and standardize enrichment outputs. Use when building automated enrichment workflows integrated with SIEM aler
- [[building-automated-malware-submission-pipeline]] *(complement)* — Builds an automated malware submission and analysis pipeline that collects suspicious files from endpoints and email gateways, submits them to sandbox environments and multi-engine scanners, and generates verdicts with IOCs for SIEM integration. Use when SOC teams need to scale malware analysis beyo
- [[building-threat-intelligence-enrichment-in-splunk]] *(similar)* — Build automated threat intelligence enrichment pipelines in Splunk Enterprise Security using lookup tables, modular inputs, and the Threat Intelligence Framework.
- [[collecting-threat-intelligence-with-misp]] *(similar)* — MISP (Malware Information Sharing Platform) is an open-source threat intelligence platform for gathering, sharing, storing, and correlating Indicators of Compromise (IOCs) of targeted attacks, threat
- [[implementing-security-information-sharing-with-stix2]] *(similar)* — Create, validate, and share STIX 2.1 threat intelligence objects using the stix2 Python library. Covers indicators, malware, campaigns, relationships, bundles, and TAXII 2.1 publishing.

- [[implementing-stix-taxii-feed-integration]] *(similar)* — STIX (Structured Threat Information eXpression) and TAXII (Trusted Automated eXchange of Intelligence Information) are OASIS open standards for representing and transporting cyber threat intelligence.
- [[performing-malware-ioc-extraction]] *(similar)* — Malware IOC extraction is the process of analyzing malicious software to identify actionable indicators of compromise including file hashes, network indicators (C2 domains, IP addresses, URLs), regist

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
