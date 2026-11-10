---
title: detecting-secure-boot-bypass
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-memory-dumps-with-volatility, analyzing-uefi-bootkit-persistence, detecting-azure-service-principal-abuse, detecting-bluetooth-low-energy-attacks, detecting-dll-sideloading-attacks, detecting-privilege-escalation-attempts, detecting-suspicious-powershell-execution]
confidence: low
---

Detect bootkits such as BlackLotus and Bootkitty and Secure Boot bypass via DBX and binary checks.

## Metadata

- **ID:** `detecting-secure-boot-bypass`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-secure-boot-bypass/SKILL.md`
- **Score:** 37.0
- **Edges:** 7

## Related Skills

- [[analyzing-memory-dumps-with-volatility]] *(similar)* — Analyzes RAM memory dumps from compromised systems using the Volatility framework to identify malicious processes, injected code, network connections, loaded modules, and extracted credentials. Supports Windows, Linux, and macOS memory forensics. Activates for requests involving memory forensics, RA
- [[detecting-azure-service-principal-abuse]] *(similar)* — Detect and investigate Azure service principal abuse including privilege escalation, credential compromise, admin consent bypass, and unauthorized enumeration in Microsoft Entra ID environments.
- [[detecting-dll-sideloading-attacks]] *(similar)* — Detect DLL side-loading attacks where adversaries place malicious DLLs alongside legitimate applications to hijack execution flow for defense evasion.
- [[detecting-privilege-escalation-attempts]] *(similar)* — Detect privilege escalation attempts including token manipulation, UAC bypass, unquoted service paths, kernel exploits, and sudo/doas abuse across Windows and Linux.
- [[detecting-suspicious-powershell-execution]] *(similar)* — Detect suspicious PowerShell execution patterns including encoded commands, download cradles, AMSI bypass attempts, and constrained language mode evasion.
- [[analyzing-uefi-bootkit-persistence]] *(complement)* — Analyzes UEFI bootkit persistence mechanisms including firmware implants in SPI flash, EFI System Partition (ESP) modifications, Secure Boot bypass techniques, and UEFI variable manipulation. Covers detection of known bootkit families (BlackLotus, LoJax, MosaicRegressor, MoonBounce, CosmicStrand), E
- [[detecting-bluetooth-low-energy-attacks]] *(similar)* — Detects and analyzes Bluetooth Low Energy (BLE) security attacks including sniffing, replay attacks, GATT enumeration abuse, and Man-in-the-Middle interception. Uses Ubertooth One and nRF52840 sniffers for packet capture, the bleak Python library for GATT service enumeration, and crackle for BLE enc

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
