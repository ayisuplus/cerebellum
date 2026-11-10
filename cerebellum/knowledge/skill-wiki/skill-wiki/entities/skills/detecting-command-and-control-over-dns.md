---
title: detecting-command-and-control-over-dns
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-cobaltstrike-malleable-c2-profiles, analyzing-typosquatting-domains-with-dnstwist, building-adversary-infrastructure-tracking-system, detecting-dnp3-protocol-anomalies, detecting-ransomware-precursors-in-network, hunting-for-cobalt-strike-beacons, hunting-for-command-and-control-beaconing, hunting-for-domain-fronting-c2-traffic]
confidence: medium
---

Detects command-and-control (C2) communications tunneled through DNS protocol including DNS tunneling tools (Iodine, dnscat2, dns2tcp, Cobalt Strike DNS beacon), domain generation algorithms (DGA), encoded payload delivery via TXT/CNAME records, and DNS beaconing patterns. Covers Shannon entropy ana

## Metadata

- **ID:** `detecting-command-and-control-over-dns`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-command-and-control-over-dns/SKILL.md`
- **Score:** 65.0
- **Edges:** 8

## Related Skills

- [[hunting-for-command-and-control-beaconing]] *(complement)* — Detect C2 beaconing patterns in network traffic using frequency analysis, jitter detection, and domain reputation to identify compromised endpoints communicating with adversary infrastructure.
- [[analyzing-cobaltstrike-malleable-c2-profiles]] *(similar)* — Parse and analyze Cobalt Strike Malleable C2 profiles using dissect.cobaltstrike and pyMalleableC2 to extract C2 indicators, detect evasion techniques, and generate network detection signatures.
- [[detecting-dnp3-protocol-anomalies]] *(similar)* — Detect anomalies in DNP3 (Distributed Network Protocol 3) communications used in SCADA systems by monitoring for unauthorized control commands, firmware update attempts, protocol violations, and deviations from baseline traffic patterns using deep packet inspection and machine learning approaches.

- [[detecting-ransomware-precursors-in-network]] *(similar)* — Detects early-stage ransomware indicators in network traffic before encryption begins, including initial access broker activity, command-and-control beaconing, credential harvesting, reconnaissance scanning, and staging behavior. Uses network detection tools (Zeek, Suricata, Arkime), SIEM correlatio
- [[hunting-for-cobalt-strike-beacons]] *(similar)* — Detect Cobalt Strike beacon network activity using default TLS certificate signatures (serial 8BB00EE), JA3/JA3S/JARM fingerprints, HTTP C2 profile pattern matching, beacon jitter analysis, and named pipe detection via Zeek, Suricata, and Python PCAP analysis.
- [[analyzing-typosquatting-domains-with-dnstwist]] *(similar)* — Detect typosquatting, homograph phishing, and brand impersonation domains using dnstwist to generate domain permutations and identify registered lookalike domains targeting your organization.
- [[building-adversary-infrastructure-tracking-system]] *(similar)* — Build an automated system to track adversary infrastructure using passive DNS, certificate transparency, WHOIS data, and IP enrichment to map and monitor threat actor command-and-control networks.
- [[hunting-for-domain-fronting-c2-traffic]] *(similar)* — Detect domain fronting C2 traffic by analyzing SNI vs HTTP Host header mismatches in proxy logs and TLS certificate discrepancies using pyOpenSSL for certificate inspection

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
