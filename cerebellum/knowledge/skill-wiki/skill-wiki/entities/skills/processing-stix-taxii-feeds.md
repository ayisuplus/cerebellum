---
title: processing-stix-taxii-feeds
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-threat-intelligence-feeds, automating-ioc-enrichment, building-ioc-defanging-and-sharing-pipeline, building-ioc-enrichment-pipeline-with-opencti, building-threat-intelligence-feed-integration, building-threat-intelligence-platform, collecting-indicators-of-compromise, collecting-threat-intelligence-with-misp, evaluating-threat-intelligence-platforms, implementing-security-information-sharing-with-stix2, implementing-stix-taxii-feed-integration]
confidence: medium
---

Processes STIX 2.1 threat intelligence bundles delivered via TAXII 2.1 servers, normalizing objects into platform-native schemas and routing them to appropriate consuming systems. Use when onboarding new TAXII collection endpoints, automating bi-directional intelligence sharing with ISACs, or buildi

## Metadata

- **ID:** `processing-stix-taxii-feeds`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/processing-stix-taxii-feeds/SKILL.md`
- **Score:** 53.0
- **Edges:** 11

## Related Skills

- [[automating-ioc-enrichment]] *(similar)* — Automates the enrichment of raw indicators of compromise with multi-source threat intelligence context using SOAR platforms, Python pipelines, or TIP playbooks to reduce analyst triage time and standardize enrichment outputs. Use when building automated enrichment workflows integrated with SIEM aler
- [[building-ioc-enrichment-pipeline-with-opencti]] *(similar)* — OpenCTI is an open-source platform for managing cyber threat intelligence knowledge, built on STIX 2.1 as its native data model. This skill covers building an automated IOC enrichment pipeline using O
- [[building-threat-intelligence-platform]] *(similar)* — Building a Threat Intelligence Platform (TIP) involves deploying and integrating multiple CTI tools into a unified system for collecting, analyzing, enriching, and disseminating threat intelligence. T
- [[collecting-indicators-of-compromise]] *(similar)* — Systematically collects, categorizes, and distributes indicators of compromise (IOCs) during and after security incidents to enable detection, blocking, and threat intelligence sharing. Covers network, host, email, and behavioral indicators using STIX/TAXII formats and threat intelligence platforms.
- [[collecting-threat-intelligence-with-misp]] *(similar)* — MISP (Malware Information Sharing Platform) is an open-source threat intelligence platform for gathering, sharing, storing, and correlating Indicators of Compromise (IOCs) of targeted attacks, threat
- [[analyzing-threat-intelligence-feeds]] *(complement)* — Analyzes structured and unstructured threat intelligence feeds to extract actionable indicators, adversary tactics, and campaign context. Use when ingesting commercial or open-source CTI feeds, evaluating feed quality, normalizing data into STIX 2.1 format, or enriching existing IOCs with campaign a
- [[building-threat-intelligence-feed-integration]] *(complement)* — Builds automated threat intelligence feed integration pipelines connecting STIX/TAXII feeds, open-source threat intel, and commercial TI platforms into SIEM and security tools for real-time IOC matching and alerting. Use when SOC teams need to operationalize threat intelligence by automating feed in
- [[implementing-stix-taxii-feed-integration]] *(complement)* — STIX (Structured Threat Information eXpression) and TAXII (Trusted Automated eXchange of Intelligence Information) are OASIS open standards for representing and transporting cyber threat intelligence.
- [[building-ioc-defanging-and-sharing-pipeline]] *(similar)* — Build an automated pipeline to defang indicators of compromise (URLs, IPs, domains, emails) for safe sharing and distribute them in STIX format through TAXII feeds and threat intelligence platforms.
- [[evaluating-threat-intelligence-platforms]] *(similar)* — Evaluates and selects Threat Intelligence Platform (TIP) products based on organizational requirements including feed integration capability, STIX/TAXII support, workflow automation, analyst interface, and total cost of ownership. Use when conducting a TIP procurement, migrating between TIP solution
- [[implementing-security-information-sharing-with-stix2]] *(similar)* — Create, validate, and share STIX 2.1 threat intelligence objects using the stix2 Python library. Covers indicators, malware, campaigns, relationships, bundles, and TAXII 2.1 publishing.


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
