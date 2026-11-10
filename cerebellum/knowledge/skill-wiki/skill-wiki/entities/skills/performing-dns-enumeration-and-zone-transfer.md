---
title: performing-dns-enumeration-and-zone-transfer
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [conducting-domain-persistence-with-dcsync, conducting-external-reconnaissance-with-osint, hunting-for-dns-based-persistence, implementing-attack-surface-management, performing-active-directory-forest-trust-attack, performing-blind-ssrf-exploitation, performing-gcp-penetration-testing-with-gcpbucketbrute, performing-subdomain-enumeration-with-subfinder]
confidence: medium
---

Enumerates DNS records, attempts zone transfers, brute-forces subdomains, and maps DNS infrastructure during authorized reconnaissance to identify attack surface, misconfigurations, and information disclosure in target domains.

## Metadata

- **ID:** `performing-dns-enumeration-and-zone-transfer`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/performing-dns-enumeration-and-zone-transfer/SKILL.md`
- **Score:** 48.0
- **Edges:** 8

## Related Skills

- [[performing-subdomain-enumeration-with-subfinder]] *(complement)* — Enumerate subdomains of target domains using ProjectDiscovery's Subfinder passive reconnaissance tool to map the attack surface during security assessments.
- [[conducting-domain-persistence-with-dcsync]] *(similar)* — Perform DCSync attacks to replicate Active Directory credentials and establish domain persistence by extracting KRBTGT, Domain Admin, and service account hashes for Golden Ticket creation.
- [[performing-active-directory-forest-trust-attack]] *(similar)* — Enumerate and audit Active Directory forest trust relationships using impacket for SID filtering analysis, trust key extraction, cross-forest SID history abuse detection, and inter-realm Kerberos ticket assessment.
- [[performing-blind-ssrf-exploitation]] *(similar)* — Detect and exploit blind Server-Side Request Forgery vulnerabilities using out-of-band techniques, DNS interactions, and timing analysis to access internal services and cloud metadata endpoints.
- [[performing-gcp-penetration-testing-with-gcpbucketbrute]] *(similar)* — Perform GCP security testing using GCPBucketBrute for storage bucket enumeration, gcloud IAM privilege escalation path analysis, and service account permission auditing
- [[hunting-for-dns-based-persistence]] *(complement)* — Hunt for DNS-based persistence mechanisms including DNS hijacking, dangling CNAME records, wildcard DNS abuse, and unauthorized zone modifications using passive DNS databases, SecurityTrails API, and DNS audit log analysis.
- [[conducting-external-reconnaissance-with-osint]] *(similar)* — Conducts external reconnaissance using Open Source Intelligence (OSINT) techniques to map an organization's external attack surface without directly interacting with target systems. The tester gathers information from public sources including DNS records, certificate transparency logs, search engine
- [[implementing-attack-surface-management]] *(similar)* — Implements external attack surface management (EASM) using Shodan, Censys, and ProjectDiscovery tools (subfinder, httpx, nuclei) for asset discovery, subdomain enumeration, service fingerprinting, and exposure scoring. Includes a weighted risk scoring algorithm based on OWASP attack surface analysis

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
