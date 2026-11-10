---
title: collecting-indicators-of-compromise
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-indicators-of-compromise, analyzing-threat-intelligence-feeds, automating-ioc-enrichment, building-ioc-defanging-and-sharing-pipeline, collecting-threat-intelligence-with-misp, correlating-threat-campaigns, performing-indicator-lifecycle-management, performing-malware-ioc-extraction, processing-stix-taxii-feeds]
confidence: medium
---

Systematically collects, categorizes, and distributes indicators of compromise (IOCs) during and after security incidents to enable detection, blocking, and threat intelligence sharing. Covers network, host, email, and behavioral indicators using STIX/TAXII formats and threat intelligence platforms.

## Metadata

- **ID:** `collecting-indicators-of-compromise`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/collecting-indicators-of-compromise/SKILL.md`
- **Score:** 45.0
- **Edges:** 9

## Related Skills

- [[collecting-threat-intelligence-with-misp]] *(complement)* — MISP (Malware Information Sharing Platform) is an open-source threat intelligence platform for gathering, sharing, storing, and correlating Indicators of Compromise (IOCs) of targeted attacks, threat
- [[analyzing-threat-intelligence-feeds]] *(similar)* — Analyzes structured and unstructured threat intelligence feeds to extract actionable indicators, adversary tactics, and campaign context. Use when ingesting commercial or open-source CTI feeds, evaluating feed quality, normalizing data into STIX 2.1 format, or enriching existing IOCs with campaign a
- [[automating-ioc-enrichment]] *(similar)* — Automates the enrichment of raw indicators of compromise with multi-source threat intelligence context using SOAR platforms, Python pipelines, or TIP playbooks to reduce analyst triage time and standardize enrichment outputs. Use when building automated enrichment workflows integrated with SIEM aler
- [[correlating-threat-campaigns]] *(similar)* — Correlates disparate security incidents, IOCs, and adversary behaviors across time and organizations to identify unified threat campaigns, attribute them to common threat actors, and extract shared indicators for improved detection. Use when multiple incidents exhibit overlapping indicators, when se
- [[performing-malware-ioc-extraction]] *(similar)* — Malware IOC extraction is the process of analyzing malicious software to identify actionable indicators of compromise including file hashes, network indicators (C2 domains, IP addresses, URLs), regist
- [[analyzing-indicators-of-compromise]] *(complement)* — Analyzes indicators of compromise (IOCs) including IP addresses, domains, file hashes, URLs, and email artifacts to determine maliciousness confidence, campaign attribution, and blocking priority. Use when triaging IOCs from phishing emails, security alerts, or external threat feeds; enriching raw I
- [[building-ioc-defanging-and-sharing-pipeline]] *(similar)* — Build an automated pipeline to defang indicators of compromise (URLs, IPs, domains, emails) for safe sharing and distribute them in STIX format through TAXII feeds and threat intelligence platforms.
- [[performing-indicator-lifecycle-management]] *(similar)* — Indicator lifecycle management tracks IOCs from initial discovery through validation, enrichment, deployment, monitoring, and eventual retirement. This skill covers implementing systematic processes f
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
