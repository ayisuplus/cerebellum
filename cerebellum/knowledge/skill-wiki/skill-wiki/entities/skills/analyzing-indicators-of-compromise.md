---
title: analyzing-indicators-of-compromise
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-malicious-url-with-urlscan, analyzing-ransomware-network-indicators, analyzing-threat-intelligence-feeds, analyzing-threat-landscape-with-misp, automating-ioc-enrichment, building-ioc-defanging-and-sharing-pipeline, collecting-indicators-of-compromise, collecting-threat-intelligence-with-misp, conducting-phishing-incident-response, correlating-threat-campaigns, investigating-phishing-email-incident, performing-indicator-lifecycle-management, performing-ip-reputation-analysis-with-shodan, performing-malware-hash-enrichment-with-virustotal, performing-malware-ioc-extraction, triaging-security-incident]
confidence: low
---

Analyzes indicators of compromise (IOCs) including IP addresses, domains, file hashes, URLs, and email artifacts to determine maliciousness confidence, campaign attribution, and blocking priority. Use when triaging IOCs from phishing emails, security alerts, or external threat feeds; enriching raw I

## Metadata

- **ID:** `analyzing-indicators-of-compromise`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/analyzing-indicators-of-compromise/SKILL.md`
- **Score:** 39.0
- **Edges:** 16

## Related Skills

- [[analyzing-threat-intelligence-feeds]] *(complement)* — Analyzes structured and unstructured threat intelligence feeds to extract actionable indicators, adversary tactics, and campaign context. Use when ingesting commercial or open-source CTI feeds, evaluating feed quality, normalizing data into STIX 2.1 format, or enriching existing IOCs with campaign a
- [[automating-ioc-enrichment]] *(complement)* — Automates the enrichment of raw indicators of compromise with multi-source threat intelligence context using SOAR platforms, Python pipelines, or TIP playbooks to reduce analyst triage time and standardize enrichment outputs. Use when building automated enrichment workflows integrated with SIEM aler
- [[collecting-indicators-of-compromise]] *(complement)* — Systematically collects, categorizes, and distributes indicators of compromise (IOCs) during and after security incidents to enable detection, blocking, and threat intelligence sharing. Covers network, host, email, and behavioral indicators using STIX/TAXII formats and threat intelligence platforms.
- [[correlating-threat-campaigns]] *(complement)* — Correlates disparate security incidents, IOCs, and adversary behaviors across time and organizations to identify unified threat campaigns, attribute them to common threat actors, and extract shared indicators for improved detection. Use when multiple incidents exhibit overlapping indicators, when se
- [[performing-malware-ioc-extraction]] *(complement)* — Malware IOC extraction is the process of analyzing malicious software to identify actionable indicators of compromise including file hashes, network indicators (C2 domains, IP addresses, URLs), regist
- [[analyzing-malicious-url-with-urlscan]] *(similar)* — URLScan.io is a free service for scanning and analyzing suspicious URLs. It captures screenshots, DOM content, HTTP transactions, JavaScript behavior, and network connections of web pages in an isolat
- [[analyzing-ransomware-network-indicators]] *(similar)* — Identify ransomware network indicators including C2 beaconing patterns, TOR exit node connections, data exfiltration flows, and encryption key exchange via Zeek conn.log and NetFlow analysis
- [[analyzing-threat-landscape-with-misp]] *(similar)* — Analyze the threat landscape using MISP (Malware Information Sharing Platform) by querying event statistics, attribute distributions, threat actor galaxy clusters, and tag trends over time. Uses PyMISP to pull event data, compute IOC type breakdowns, identify top threat actors and malware families, 
- [[building-ioc-defanging-and-sharing-pipeline]] *(similar)* — Build an automated pipeline to defang indicators of compromise (URLs, IPs, domains, emails) for safe sharing and distribute them in STIX format through TAXII feeds and threat intelligence platforms.
- [[collecting-threat-intelligence-with-misp]] *(similar)* — MISP (Malware Information Sharing Platform) is an open-source threat intelligence platform for gathering, sharing, storing, and correlating Indicators of Compromise (IOCs) of targeted attacks, threat
- [[conducting-phishing-incident-response]] *(similar)* — Responds to phishing incidents by analyzing reported emails, extracting indicators, assessing credential compromise, quarantining malicious messages across the organization, and remediating affected accounts. Covers email header analysis, URL/attachment sandboxing, and mailbox-wide purge operations.
- [[investigating-phishing-email-incident]] *(similar)* — Investigates phishing email incidents from initial user report through header analysis, URL/attachment detonation, impacted user identification, and containment actions using SOC tools like Splunk, Microsoft Defender, and sandbox analysis platforms. Use when a reported phishing email requires full i
- [[performing-indicator-lifecycle-management]] *(similar)* — Indicator lifecycle management tracks IOCs from initial discovery through validation, enrichment, deployment, monitoring, and eventual retirement. This skill covers implementing systematic processes f
- [[performing-ip-reputation-analysis-with-shodan]] *(similar)* — Analyze IP address reputation using the Shodan API to identify open ports, running services, known vulnerabilities, and hosting context for threat intelligence enrichment and incident triage.
- [[performing-malware-hash-enrichment-with-virustotal]] *(similar)* — Enrich malware file hashes using the VirusTotal API to retrieve detection rates, behavioral analysis, YARA matches, and contextual threat intelligence for incident triage and IOC validation.
- [[triaging-security-incident]] *(similar)* — Performs initial triage of security incidents to determine severity, scope, and required response actions using the NIST SP 800-61r3 and SANS PICERL frameworks. Classifies incidents by type, assigns priority based on business impact, and routes to appropriate response teams. Activates for requests i

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
