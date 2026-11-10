---
title: analyzing-cobaltstrike-malleable-c2-profiles
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-malware-family-relationships-with-malpedia, analyzing-network-flow-data-with-netflow, analyzing-network-packets-with-scapy, analyzing-windows-prefetch-with-python, detecting-command-and-control-over-dns, extracting-config-from-agent-tesla-rat, hunting-for-cobalt-strike-beacons, hunting-for-command-and-control-beaconing]
confidence: low
---

Parse and analyze Cobalt Strike Malleable C2 profiles using dissect.cobaltstrike and pyMalleableC2 to extract C2 indicators, detect evasion techniques, and generate network detection signatures.

## Metadata

- **ID:** `analyzing-cobaltstrike-malleable-c2-profiles`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/analyzing-cobaltstrike-malleable-c2-profiles/SKILL.md`
- **Score:** 27.0
- **Edges:** 8

## Related Skills

- [[analyzing-network-flow-data-with-netflow]] *(similar)* — Parse NetFlow v9 and IPFIX records to detect volumetric anomalies, port scanning, data exfiltration, and C2 beaconing patterns. Uses the Python netflow library to decode flow records, builds traffic baselines, and applies statistical analysis to identify flows with abnormal byte counts, connection d
- [[analyzing-network-packets-with-scapy]] *(similar)* — Craft, send, sniff, and dissect network packets using Scapy for protocol analysis, network reconnaissance, and traffic anomaly detection in authorized security testing
- [[analyzing-windows-prefetch-with-python]] *(similar)* — Parse Windows Prefetch files using the windowsprefetch Python library to reconstruct application execution history, detect renamed or masquerading binaries, and identify suspicious program execution patterns.
- [[hunting-for-cobalt-strike-beacons]] *(similar)* — Detect Cobalt Strike beacon network activity using default TLS certificate signatures (serial 8BB00EE), JA3/JA3S/JARM fingerprints, HTTP C2 profile pattern matching, beacon jitter analysis, and named pipe detection via Zeek, Suricata, and Python PCAP analysis.
- [[hunting-for-command-and-control-beaconing]] *(similar)* — Detect C2 beaconing patterns in network traffic using frequency analysis, jitter detection, and domain reputation to identify compromised endpoints communicating with adversary infrastructure.
- [[analyzing-malware-family-relationships-with-malpedia]] *(similar)* — Use the Malpedia platform and API to research malware family relationships, track variant evolution, link families to threat actors, and integrate YARA rules for detection across malware lineages.
- [[detecting-command-and-control-over-dns]] *(similar)* — Detects command-and-control (C2) communications tunneled through DNS protocol including DNS tunneling tools (Iodine, dnscat2, dns2tcp, Cobalt Strike DNS beacon), domain generation algorithms (DGA), encoded payload delivery via TXT/CNAME records, and DNS beaconing patterns. Covers Shannon entropy ana
- [[extracting-config-from-agent-tesla-rat]] *(similar)* — Extract embedded configuration from Agent Tesla RAT samples including SMTP/FTP/Telegram exfiltration credentials, keylogger settings, and C2 endpoints using .NET decompilation and memory analysis.

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
