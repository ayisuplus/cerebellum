---
title: collecting-threat-intelligence-with-misp
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-indicators-of-compromise, analyzing-threat-intelligence-feeds, analyzing-threat-landscape-with-misp, building-ioc-defanging-and-sharing-pipeline, building-ioc-enrichment-pipeline-with-opencti, building-threat-intelligence-enrichment-in-splunk, building-threat-intelligence-platform, collecting-indicators-of-compromise, correlating-threat-campaigns, generating-threat-intelligence-reports, implementing-security-information-sharing-with-stix2, implementing-stix-taxii-feed-integration, implementing-threat-intelligence-lifecycle-management, performing-ip-reputation-analysis-with-shodan, performing-malware-ioc-extraction, performing-threat-hunting-with-yara-rules, processing-stix-taxii-feeds]
confidence: low
---

MISP (Malware Information Sharing Platform) is an open-source threat intelligence platform for gathering, sharing, storing, and correlating Indicators of Compromise (IOCs) of targeted attacks, threat

## Metadata

- **ID:** `collecting-threat-intelligence-with-misp`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/collecting-threat-intelligence-with-misp/SKILL.md`
- **Score:** 35.0
- **Edges:** 17

## Related Skills

- [[analyzing-indicators-of-compromise]] *(similar)* — Analyzes indicators of compromise (IOCs) including IP addresses, domains, file hashes, URLs, and email artifacts to determine maliciousness confidence, campaign attribution, and blocking priority. Use when triaging IOCs from phishing emails, security alerts, or external threat feeds; enriching raw I
- [[analyzing-threat-intelligence-feeds]] *(similar)* — Analyzes structured and unstructured threat intelligence feeds to extract actionable indicators, adversary tactics, and campaign context. Use when ingesting commercial or open-source CTI feeds, evaluating feed quality, normalizing data into STIX 2.1 format, or enriching existing IOCs with campaign a
- [[building-ioc-defanging-and-sharing-pipeline]] *(similar)* — Build an automated pipeline to defang indicators of compromise (URLs, IPs, domains, emails) for safe sharing and distribute them in STIX format through TAXII feeds and threat intelligence platforms.
- [[correlating-threat-campaigns]] *(similar)* — Correlates disparate security incidents, IOCs, and adversary behaviors across time and organizations to identify unified threat campaigns, attribute them to common threat actors, and extract shared indicators for improved detection. Use when multiple incidents exhibit overlapping indicators, when se
- [[performing-malware-ioc-extraction]] *(similar)* — Malware IOC extraction is the process of analyzing malicious software to identify actionable indicators of compromise including file hashes, network indicators (C2 domains, IP addresses, URLs), regist
- [[analyzing-threat-landscape-with-misp]] *(complement)* — Analyze the threat landscape using MISP (Malware Information Sharing Platform) by querying event statistics, attribute distributions, threat actor galaxy clusters, and tag trends over time. Uses PyMISP to pull event data, compute IOC type breakdowns, identify top threat actors and malware families, 
- [[building-threat-intelligence-platform]] *(complement)* — Building a Threat Intelligence Platform (TIP) involves deploying and integrating multiple CTI tools into a unified system for collecting, analyzing, enriching, and disseminating threat intelligence. T
- [[collecting-indicators-of-compromise]] *(complement)* — Systematically collects, categorizes, and distributes indicators of compromise (IOCs) during and after security incidents to enable detection, blocking, and threat intelligence sharing. Covers network, host, email, and behavioral indicators using STIX/TAXII formats and threat intelligence platforms.
- [[building-ioc-enrichment-pipeline-with-opencti]] *(similar)* — OpenCTI is an open-source platform for managing cyber threat intelligence knowledge, built on STIX 2.1 as its native data model. This skill covers building an automated IOC enrichment pipeline using O
- [[building-threat-intelligence-enrichment-in-splunk]] *(similar)* — Build automated threat intelligence enrichment pipelines in Splunk Enterprise Security using lookup tables, modular inputs, and the Threat Intelligence Framework.
- [[generating-threat-intelligence-reports]] *(similar)* — Generates structured cyber threat intelligence reports at strategic, operational, and tactical levels tailored to specific audiences including executives, security operations teams, and technical analysts. Use when producing finished intelligence products from raw collection data, creating sector th
- [[implementing-security-information-sharing-with-stix2]] *(similar)* — Create, validate, and share STIX 2.1 threat intelligence objects using the stix2 Python library. Covers indicators, malware, campaigns, relationships, bundles, and TAXII 2.1 publishing.

- [[implementing-stix-taxii-feed-integration]] *(similar)* — STIX (Structured Threat Information eXpression) and TAXII (Trusted Automated eXchange of Intelligence Information) are OASIS open standards for representing and transporting cyber threat intelligence.
- [[implementing-threat-intelligence-lifecycle-management]] *(similar)* — Implement a structured threat intelligence lifecycle encompassing planning, collection, processing, analysis, dissemination, and feedback stages to produce actionable intelligence for organizational decision-making.
- [[performing-ip-reputation-analysis-with-shodan]] *(similar)* — Analyze IP address reputation using the Shodan API to identify open ports, running services, known vulnerabilities, and hosting context for threat intelligence enrichment and incident triage.
- [[performing-threat-hunting-with-yara-rules]] *(similar)* — Use YARA pattern-matching rules to hunt for malware, suspicious files, and indicators of compromise across filesystems and memory dumps. Covers rule authoring, yara-python scanning, and integration with threat intel feeds.

- [[processing-stix-taxii-feeds]] *(similar)* — Processes STIX 2.1 threat intelligence bundles delivered via TAXII 2.1 servers, normalizing objects into platform-native schemas and routing them to appropriate consuming systems. Use when onboarding new TAXII collection endpoints, automating bi-directional intelligence sharing with ISACs, or buildi

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
