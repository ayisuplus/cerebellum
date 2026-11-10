---
title: hunting-for-command-and-control-beaconing
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-cobaltstrike-malleable-c2-profiles, analyzing-network-flow-data-with-netflow, building-adversary-infrastructure-tracking-system, building-attack-pattern-library-from-cti-reports, detecting-beaconing-patterns-with-zeek, detecting-command-and-control-over-dns, detecting-mimikatz-execution-patterns, detecting-mobile-malware-behavior, detecting-ransomware-precursors-in-network, detecting-shadow-api-endpoints, hunting-for-cobalt-strike-beacons, hunting-for-domain-fronting-c2-traffic, hunting-for-ntlm-relay-attacks, hunting-for-spearphishing-indicators, hunting-for-unusual-network-connections, implementing-network-traffic-analysis-with-arkime, mapping-mitre-attack-techniques, scanning-network-with-nmap-advanced]
confidence: low
---

Detect C2 beaconing patterns in network traffic using frequency analysis, jitter detection, and domain reputation to identify compromised endpoints communicating with adversary infrastructure.

## Metadata

- **ID:** `hunting-for-command-and-control-beaconing`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/hunting-for-command-and-control-beaconing/SKILL.md`
- **Score:** 31.0
- **Edges:** 18

## Related Skills

- [[hunting-for-unusual-network-connections]] *(complement)* — Hunt for unusual network connections by analyzing outbound traffic patterns, rare destinations, non-standard ports, and anomalous connection frequencies from endpoints.
- [[analyzing-network-flow-data-with-netflow]] *(similar)* — Parse NetFlow v9 and IPFIX records to detect volumetric anomalies, port scanning, data exfiltration, and C2 beaconing patterns. Uses the Python netflow library to decode flow records, builds traffic baselines, and applies statistical analysis to identify flows with abnormal byte counts, connection d
- [[hunting-for-ntlm-relay-attacks]] *(similar)* — Detect NTLM relay attacks by analyzing Windows Event 4624 logon type 3 with NTLMSSP authentication, identifying IP-to-hostname mismatches, Responder traffic signatures, SMB signing status, and suspicious authentication patterns across the domain.
- [[hunting-for-spearphishing-indicators]] *(similar)* — Hunt for spearphishing campaign indicators across email logs, endpoint telemetry, and network data to detect targeted email attacks.
- [[implementing-network-traffic-analysis-with-arkime]] *(similar)* — Deploy and query Arkime (formerly Moloch) for full packet capture network traffic analysis. Uses the Arkime API v3 to search sessions, download PCAPs, analyze connection patterns, detect beaconing behavior, and identify suspicious network flows. Monitors DNS queries, HTTP traffic, and TLS certificat
- [[detecting-beaconing-patterns-with-zeek]] *(complement)* — Performs statistical analysis of Zeek conn.log connection intervals to detect C2 beaconing patterns. Uses the ZAT library to load Zeek logs into Pandas DataFrames, calculates inter-arrival time standard deviation, and flags periodic connections with low jitter. Use when hunting for command-and-contr
- [[detecting-command-and-control-over-dns]] *(complement)* — Detects command-and-control (C2) communications tunneled through DNS protocol including DNS tunneling tools (Iodine, dnscat2, dns2tcp, Cobalt Strike DNS beacon), domain generation algorithms (DGA), encoded payload delivery via TXT/CNAME records, and DNS beaconing patterns. Covers Shannon entropy ana
- [[hunting-for-cobalt-strike-beacons]] *(complement)* — Detect Cobalt Strike beacon network activity using default TLS certificate signatures (serial 8BB00EE), JA3/JA3S/JARM fingerprints, HTTP C2 profile pattern matching, beacon jitter analysis, and named pipe detection via Zeek, Suricata, and Python PCAP analysis.
- [[analyzing-cobaltstrike-malleable-c2-profiles]] *(similar)* — Parse and analyze Cobalt Strike Malleable C2 profiles using dissect.cobaltstrike and pyMalleableC2 to extract C2 indicators, detect evasion techniques, and generate network detection signatures.
- [[building-adversary-infrastructure-tracking-system]] *(similar)* — Build an automated system to track adversary infrastructure using passive DNS, certificate transparency, WHOIS data, and IP enrichment to map and monitor threat actor command-and-control networks.
- [[building-attack-pattern-library-from-cti-reports]] *(similar)* — Extract and catalog attack patterns from cyber threat intelligence reports into a structured STIX-based library mapped to MITRE ATT&CK for detection engineering and threat-informed defense.
- [[detecting-mimikatz-execution-patterns]] *(similar)* — Detect Mimikatz execution through command-line patterns, LSASS access signatures, binary indicators, and in-memory detection of known modules.
- [[detecting-mobile-malware-behavior]] *(similar)* — Detects and analyzes malicious behavior in mobile applications through behavioral analysis, permission abuse detection, network traffic monitoring, and dynamic instrumentation. Use when analyzing suspicious mobile applications for data exfiltration, command-and-control communication, credential stea
- [[detecting-ransomware-precursors-in-network]] *(similar)* — Detects early-stage ransomware indicators in network traffic before encryption begins, including initial access broker activity, command-and-control beaconing, credential harvesting, reconnaissance scanning, and staging behavior. Uses network detection tools (Zeek, Suricata, Arkime), SIEM correlatio
- [[detecting-shadow-api-endpoints]] *(similar)* — Discover and inventory shadow API endpoints that operate outside documented specifications using traffic analysis, code scanning, and API discovery platforms.
- [[hunting-for-domain-fronting-c2-traffic]] *(similar)* — Detect domain fronting C2 traffic by analyzing SNI vs HTTP Host header mismatches in proxy logs and TLS certificate discrepancies using pyOpenSSL for certificate inspection
- [[mapping-mitre-attack-techniques]] *(similar)* — Maps observed adversary behaviors, security alerts, and detection rules to MITRE ATT&CK techniques and sub-techniques to quantify detection coverage and guide control prioritization. Use when building an ATT&CK-based coverage heatmap, tagging SIEM alerts with technique IDs, aligning security control
- [[scanning-network-with-nmap-advanced]] *(similar)* — Performs advanced network reconnaissance using Nmap's scripting engine, timing controls, evasion techniques, and output parsing to discover hosts, enumerate services, detect vulnerabilities, and fingerprint operating systems across authorized target networks.


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
