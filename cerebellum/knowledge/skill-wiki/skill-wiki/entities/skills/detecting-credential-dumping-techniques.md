---
title: detecting-credential-dumping-techniques
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-windows-shellbag-artifacts, configuring-windows-event-logging-for-detection, deploying-active-directory-honeytokens, detecting-evasion-techniques-in-endpoint-logs, detecting-golden-ticket-forgery, detecting-kerberoasting-attacks, detecting-living-off-the-land-attacks, detecting-malicious-scheduled-tasks-with-sysmon, detecting-mimikatz-execution-patterns, detecting-pass-the-hash-attacks, detecting-process-hollowing-technique, detecting-rdp-brute-force-attacks, detecting-service-account-abuse, detecting-wmi-persistence, extracting-config-from-agent-tesla-rat, extracting-windows-event-logs-artifacts, hunting-evtx-with-chainsaw, hunting-for-ntlm-relay-attacks, hunting-for-registry-run-key-persistence, hunting-for-unusual-service-installations, implementing-siem-correlation-rules-for-apt, mapping-mitre-attack-techniques]
confidence: low
---

Detect LSASS credential dumping, SAM database extraction, and NTDS.dit theft using Sysmon Event ID 10, Windows Security logs, and SIEM correlation rules

## Metadata

- **ID:** `detecting-credential-dumping-techniques`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-credential-dumping-techniques/SKILL.md`
- **Score:** 27.0
- **Edges:** 22

## Related Skills

- [[detecting-pass-the-hash-attacks]] *(complement)* — Detect Pass-the-Hash attacks by analyzing NTLM authentication patterns, identifying Type 3 logons with NTLM where Kerberos is expected, and correlating with credential dumping.
- [[detecting-malicious-scheduled-tasks-with-sysmon]] *(similar)* — Detect malicious scheduled task creation and modification using Sysmon Event IDs 1 (Process Create for schtasks.exe), 11 (File Create for task XML), and Windows Security Event 4698/4702. The analyst correlates task creation with suspicious parent processes, public directory paths, and encoded comman
- [[detecting-mimikatz-execution-patterns]] *(similar)* — Detect Mimikatz execution through command-line patterns, LSASS access signatures, binary indicators, and in-memory detection of known modules.
- [[hunting-for-ntlm-relay-attacks]] *(similar)* — Detect NTLM relay attacks by analyzing Windows Event 4624 logon type 3 with NTLMSSP authentication, identifying IP-to-hostname mismatches, Responder traffic signatures, SMB signing status, and suspicious authentication patterns across the domain.
- [[implementing-siem-correlation-rules-for-apt]] *(similar)* — Write multi-event correlation rules that detect APT lateral movement by chaining Windows authentication events, process execution telemetry, and network connection logs across hosts. Uses Splunk SPL and Sigma rule format to correlate Event IDs 4624, 4648, 4688, and Sysmon Events 1/3 within sliding t
- [[analyzing-windows-shellbag-artifacts]] *(similar)* — Analyze Windows Shellbag registry artifacts to reconstruct folder browsing activity, detect access to removable media and network shares, and establish user interaction with directories even after deletion using SBECmd and ShellBags Explorer.
- [[configuring-windows-event-logging-for-detection]] *(similar)* — Configures Windows Event Logging with advanced audit policies to generate high-fidelity security events for threat detection and forensic investigation. Use when enabling audit policies for logon events, process creation, privilege use, and object access to feed SIEM detection rules. Activates for r
- [[deploying-active-directory-honeytokens]] *(similar)* — Deploys deception-based honeytokens in Active Directory including fake privileged accounts with AdminCount=1, fake SPNs for Kerberoasting detection (honeyroasting), decoy GPOs with cpassword traps, and fake BloodHound paths. Monitors Windows Security Event IDs 4769, 4625, 4662, 5136 for honeytoken i
- [[detecting-evasion-techniques-in-endpoint-logs]] *(similar)* — Detects defense evasion techniques used by adversaries in endpoint logs including log tampering, timestomping, process injection, and security tool disabling. Use when investigating suspicious endpoint behavior, building detection rules for evasion tactics, or conducting threat hunting for stealthy 
- [[detecting-golden-ticket-forgery]] *(similar)* — Detect Kerberos Golden Ticket forgery by analyzing Windows Event ID 4769 for RC4 encryption downgrades (0x17), abnormal ticket lifetimes, and krbtgt account anomalies in Splunk and Elastic SIEM
- [[detecting-kerberoasting-attacks]] *(similar)* — Detect Kerberoasting attacks by monitoring for anomalous Kerberos TGS requests targeting service accounts with SPNs for offline password cracking.
- [[detecting-living-off-the-land-attacks]] *(similar)* — Detect abuse of legitimate Windows binaries (LOLBins) used for living off the land attacks. Monitors process creation, command-line arguments, and parent-child relationships to identify suspicious LOLBin execution patterns.

- [[detecting-process-hollowing-technique]] *(similar)* — Detect process hollowing (T1055.012) by analyzing memory-mapped sections, hollowed process indicators, and parent-child process anomalies in EDR telemetry.
- [[detecting-rdp-brute-force-attacks]] *(similar)* — Detect RDP brute force attacks by analyzing Windows Security Event Logs for failed authentication patterns (Event ID 4625), successful logons after failures (Event ID 4624), NLA failures, and source IP frequency analysis.
- [[detecting-service-account-abuse]] *(similar)* — Detect abuse of service accounts through anomalous interactive logons, privilege escalation, lateral movement, and unauthorized access patterns.
- [[detecting-wmi-persistence]] *(similar)* — Detect WMI event subscription persistence by analyzing Sysmon Event IDs 19, 20, and 21 for malicious EventFilter, EventConsumer, and FilterToConsumerBinding creation.
- [[extracting-config-from-agent-tesla-rat]] *(similar)* — Extract embedded configuration from Agent Tesla RAT samples including SMTP/FTP/Telegram exfiltration credentials, keylogger settings, and C2 endpoints using .NET decompilation and memory analysis.
- [[extracting-windows-event-logs-artifacts]] *(similar)* — Extract, parse, and analyze Windows Event Logs (EVTX) using Chainsaw, Hayabusa, and EvtxECmd to detect lateral movement, persistence, and privilege escalation.
- [[hunting-evtx-with-chainsaw]] *(similar)* — Perform rapid Sigma and keyword hunting across Windows event logs with Chainsaw.
- [[hunting-for-registry-run-key-persistence]] *(similar)* — Detect MITRE ATT&CK T1547.001 registry Run key persistence by analyzing Sysmon Event ID 13 logs and registry queries to identify malicious auto-start entries.
- [[hunting-for-unusual-service-installations]] *(similar)* — Detect suspicious Windows service installations (MITRE ATT&CK T1543.003) by parsing System event logs for Event ID 7045, analyzing service binary paths, and identifying indicators of persistence mechanisms.
- [[mapping-mitre-attack-techniques]] *(similar)* — Maps observed adversary behaviors, security alerts, and detection rules to MITRE ATT&CK techniques and sub-techniques to quantify detection coverage and guide control prioritization. Use when building an ATT&CK-based coverage heatmap, tagging SIEM alerts with technique IDs, aligning security control

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
