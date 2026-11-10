---
title: detecting-ransomware-precursors-in-network
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [configuring-suricata-for-network-monitoring, detecting-command-and-control-over-dns, detecting-lateral-movement-with-zeek, detecting-mobile-malware-behavior, detecting-network-anomalies-with-zeek, detecting-network-scanning-with-ids-signatures, detecting-ransomware-encryption-behavior, hunting-for-cobalt-strike-beacons, hunting-for-command-and-control-beaconing, hunting-for-data-staging-before-exfiltration, hunting-for-spearphishing-indicators, implementing-network-traffic-analysis-with-arkime, implementing-ransomware-kill-switch-detection, monitoring-scada-modbus-traffic-anomalies]
confidence: medium
---

Detects early-stage ransomware indicators in network traffic before encryption begins, including initial access broker activity, command-and-control beaconing, credential harvesting, reconnaissance scanning, and staging behavior. Uses network detection tools (Zeek, Suricata, Arkime), SIEM correlatio

## Metadata

- **ID:** `detecting-ransomware-precursors-in-network`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-ransomware-precursors-in-network/SKILL.md`
- **Score:** 48.0
- **Edges:** 14

## Related Skills

- [[configuring-suricata-for-network-monitoring]] *(similar)* — Deploys and configures Suricata IDS/IPS with Emerging Threats rulesets, EVE JSON logging, and custom rules for real-time network traffic inspection, threat detection, and integration with SIEM platforms for centralized security monitoring.

- [[hunting-for-cobalt-strike-beacons]] *(similar)* — Detect Cobalt Strike beacon network activity using default TLS certificate signatures (serial 8BB00EE), JA3/JA3S/JARM fingerprints, HTTP C2 profile pattern matching, beacon jitter analysis, and named pipe detection via Zeek, Suricata, and Python PCAP analysis.
- [[hunting-for-command-and-control-beaconing]] *(similar)* — Detect C2 beaconing patterns in network traffic using frequency analysis, jitter detection, and domain reputation to identify compromised endpoints communicating with adversary infrastructure.
- [[hunting-for-spearphishing-indicators]] *(similar)* — Hunt for spearphishing campaign indicators across email logs, endpoint telemetry, and network data to detect targeted email attacks.
- [[implementing-network-traffic-analysis-with-arkime]] *(similar)* — Deploy and query Arkime (formerly Moloch) for full packet capture network traffic analysis. Uses the Arkime API v3 to search sessions, download PCAPs, analyze connection patterns, detect beaconing behavior, and identify suspicious network flows. Monitors DNS queries, HTTP traffic, and TLS certificat
- [[detecting-network-anomalies-with-zeek]] *(complement)* — Deploys and configures Zeek (formerly Bro) network security monitor to passively analyze network traffic, generate structured logs, detect anomalous behavior, and create custom detection scripts for threat hunting and incident response.

- [[detecting-command-and-control-over-dns]] *(similar)* — Detects command-and-control (C2) communications tunneled through DNS protocol including DNS tunneling tools (Iodine, dnscat2, dns2tcp, Cobalt Strike DNS beacon), domain generation algorithms (DGA), encoded payload delivery via TXT/CNAME records, and DNS beaconing patterns. Covers Shannon entropy ana
- [[detecting-lateral-movement-with-zeek]] *(similar)* — Detect lateral movement in network traffic using Zeek (formerly Bro) log analysis. Parses conn.log, smb_mapping.log, smb_files.log, dce_rpc.log, kerberos.log, and ntlm.log to identify SMB file transfers, NTLM account spray activity, remote service execution, and anomalous internal connections.

- [[detecting-mobile-malware-behavior]] *(similar)* — Detects and analyzes malicious behavior in mobile applications through behavioral analysis, permission abuse detection, network traffic monitoring, and dynamic instrumentation. Use when analyzing suspicious mobile applications for data exfiltration, command-and-control communication, credential stea
- [[detecting-network-scanning-with-ids-signatures]] *(similar)* — Detect network reconnaissance and port scanning using Suricata and Snort IDS signatures, threshold-based detection rules, and traffic anomaly analysis to identify Nmap, Masscan, and custom scanning activity.
- [[detecting-ransomware-encryption-behavior]] *(similar)* — Detects ransomware encryption activity in real time using entropy analysis, file system I/O monitoring, and behavioral heuristics. Identifies mass file modification patterns, abnormal entropy spikes in written data, and suspicious process behavior characteristic of ransomware encryption routines. Ac
- [[hunting-for-data-staging-before-exfiltration]] *(similar)* — Detect data staging activity before exfiltration by monitoring for archive creation with 7-Zip/RAR, unusual temp folder access, large file consolidation, and staging directory patterns via EDR and process telemetry
- [[implementing-ransomware-kill-switch-detection]] *(similar)* — Detects and exploits ransomware kill switch mechanisms including mutex-based execution guards, domain-based kill switches, and registry-based termination checks. Implements proactive mutex vaccination and kill switch domain monitoring to prevent ransomware from executing. Activates for requests invo
- [[monitoring-scada-modbus-traffic-anomalies]] *(similar)* — Monitors Modbus TCP traffic on SCADA and ICS networks to detect anomalous function code usage, unauthorized register writes, and suspicious communication patterns. The analyst uses deep packet inspection with pymodbus, Scapy, and Zeek to baseline normal PLC/RTU communication behavior, then applies s

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
