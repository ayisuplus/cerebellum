---
title: conducting-phishing-incident-response
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-indicators-of-compromise, analyzing-outlook-pst-for-email-forensics, conducting-cloud-incident-response, conducting-malware-incident-response, conducting-post-incident-lessons-learned, implementing-google-workspace-phishing-protection, implementing-proofpoint-email-security-gateway, implementing-soar-playbook-for-phishing, investigating-phishing-email-incident, performing-insider-threat-investigation, triaging-security-incident]
confidence: medium
---

Responds to phishing incidents by analyzing reported emails, extracting indicators, assessing credential compromise, quarantining malicious messages across the organization, and remediating affected accounts. Covers email header analysis, URL/attachment sandboxing, and mailbox-wide purge operations.

## Metadata

- **ID:** `conducting-phishing-incident-response`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/conducting-phishing-incident-response/SKILL.md`
- **Score:** 52.0
- **Edges:** 11

## Related Skills

- [[investigating-phishing-email-incident]] *(complement)* — Investigates phishing email incidents from initial user report through header analysis, URL/attachment detonation, impacted user identification, and containment actions using SOC tools like Splunk, Microsoft Defender, and sandbox analysis platforms. Use when a reported phishing email requires full i
- [[analyzing-indicators-of-compromise]] *(similar)* — Analyzes indicators of compromise (IOCs) including IP addresses, domains, file hashes, URLs, and email artifacts to determine maliciousness confidence, campaign attribution, and blocking priority. Use when triaging IOCs from phishing emails, security alerts, or external threat feeds; enriching raw I
- [[analyzing-outlook-pst-for-email-forensics]] *(similar)* — Analyze Microsoft Outlook PST and OST files for email forensic evidence including message content, headers, attachments, deleted items, and metadata using libpff, pst-utils, and forensic email analysis tools for legal investigations and incident response.
- [[implementing-proofpoint-email-security-gateway]] *(similar)* — Deploy and configure Proofpoint Email Protection as a secure email gateway to detect and block phishing, malware, BEC, and spam before messages reach user inboxes.
- [[implementing-soar-playbook-for-phishing]] *(similar)* — Automate phishing incident response using Splunk SOAR REST API to create containers, add artifacts, and trigger playbooks
- [[conducting-malware-incident-response]] *(complement)* — Responds to malware infections across enterprise endpoints by identifying the malware family, determining infection vectors, assessing spread, and executing eradication procedures. Covers the full lifecycle from detection through containment, analysis, removal, and recovery. Activates for requests i
- [[conducting-cloud-incident-response]] *(similar)* — Responds to security incidents in cloud environments (AWS, Azure, GCP) by performing identity-based containment, cloud-native log analysis, resource isolation, and forensic evidence acquisition adapted for ephemeral cloud infrastructure. Activates for requests involving cloud incident response, AWS 
- [[conducting-post-incident-lessons-learned]] *(similar)* — Facilitate structured post-incident reviews to identify root causes, document what worked and failed, and produce actionable recommendations to improve future incident response.
- [[implementing-google-workspace-phishing-protection]] *(similar)* — Configure Google Workspace advanced phishing and malware protection settings including pre-delivery scanning, attachment protection, spoofing detection, and Enhanced Safe Browsing.
- [[performing-insider-threat-investigation]] *(similar)* — Investigates insider threat incidents involving employees, contractors, or trusted partners who misuse authorized access to steal data, sabotage systems, or violate security policies. Combines digital forensics, user behavior analytics, and HR/legal coordination to build an evidence-based case. Acti
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
