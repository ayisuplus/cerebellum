---
title: implementing-network-traffic-baselining
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-network-flow-data-with-netflow, analyzing-network-packets-with-scapy, detecting-aws-cloudtrail-anomalies, detecting-beaconing-patterns-with-zeek, detecting-network-anomalies-with-zeek, detecting-shadow-it-cloud-usage, implementing-network-traffic-analysis-with-arkime, monitoring-scada-modbus-traffic-anomalies]
confidence: low
---

Build network traffic baselines from NetFlow/IPFIX data using Python pandas for statistical analysis, z-score anomaly detection, and hourly/daily traffic pattern profiling

## Metadata

- **ID:** `implementing-network-traffic-baselining`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/implementing-network-traffic-baselining/SKILL.md`
- **Score:** 27.0
- **Edges:** 8

## Related Skills

- [[analyzing-network-packets-with-scapy]] *(similar)* — Craft, send, sniff, and dissect network packets using Scapy for protocol analysis, network reconnaissance, and traffic anomaly detection in authorized security testing
- [[detecting-aws-cloudtrail-anomalies]] *(similar)* — Detect unusual API call patterns in AWS CloudTrail logs using boto3, statistical baselining, and behavioral analysis to identify credential compromise, privilege escalation, and unauthorized resource access.
- [[detecting-beaconing-patterns-with-zeek]] *(similar)* — Performs statistical analysis of Zeek conn.log connection intervals to detect C2 beaconing patterns. Uses the ZAT library to load Zeek logs into Pandas DataFrames, calculates inter-arrival time standard deviation, and flags periodic connections with low jitter. Use when hunting for command-and-contr
- [[detecting-network-anomalies-with-zeek]] *(similar)* — Deploys and configures Zeek (formerly Bro) network security monitor to passively analyze network traffic, generate structured logs, detect anomalous behavior, and create custom detection scripts for threat hunting and incident response.

- [[monitoring-scada-modbus-traffic-anomalies]] *(similar)* — Monitors Modbus TCP traffic on SCADA and ICS networks to detect anomalous function code usage, unauthorized register writes, and suspicious communication patterns. The analyst uses deep packet inspection with pymodbus, Scapy, and Zeek to baseline normal PLC/RTU communication behavior, then applies s
- [[analyzing-network-flow-data-with-netflow]] *(complement)* — Parse NetFlow v9 and IPFIX records to detect volumetric anomalies, port scanning, data exfiltration, and C2 beaconing patterns. Uses the Python netflow library to decode flow records, builds traffic baselines, and applies statistical analysis to identify flows with abnormal byte counts, connection d
- [[detecting-shadow-it-cloud-usage]] *(similar)* — Detect unauthorized SaaS and cloud service usage (shadow IT) by analyzing proxy logs, DNS query logs, and netflow data using Python pandas for traffic pattern analysis and domain classification.
- [[implementing-network-traffic-analysis-with-arkime]] *(similar)* — Deploy and query Arkime (formerly Moloch) for full packet capture network traffic analysis. Uses the Arkime API v3 to search sessions, download PCAPs, analyze connection patterns, detect beaconing behavior, and identify suspicious network flows. Monitors DNS queries, HTTP traffic, and TLS certificat

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
