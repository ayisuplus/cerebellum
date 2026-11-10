---
title: performing-bluetooth-security-assessment
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [auditing-uefi-firmware-with-chipsec, detecting-bluetooth-low-energy-attacks, performing-agentless-vulnerability-scanning, performing-android-app-static-analysis-with-mobsf, performing-authenticated-scan-with-openvas, performing-aws-account-enumeration-with-scout-suite, performing-cryptographic-audit-of-application, performing-ios-app-security-assessment, performing-iot-security-assessment, performing-ot-vulnerability-scanning-safely, performing-post-quantum-cryptography-migration, performing-scada-hmi-security-assessment, performing-security-headers-audit, performing-ssl-tls-security-assessment]
confidence: low
---

Assess Bluetooth Low Energy device security by scanning, enumerating GATT services, and detecting vulnerabilities

## Metadata

- **ID:** `performing-bluetooth-security-assessment`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/performing-bluetooth-security-assessment/SKILL.md`
- **Score:** 32.0
- **Edges:** 14

## Related Skills

- [[detecting-bluetooth-low-energy-attacks]] *(bridge)* — Detects and analyzes Bluetooth Low Energy (BLE) security attacks including sniffing, replay attacks, GATT enumeration abuse, and Man-in-the-Middle interception. Uses Ubertooth One and nRF52840 sniffers for packet capture, the bleak Python library for GATT service enumeration, and crackle for BLE enc
- [[performing-iot-security-assessment]] *(complement)* — Performs comprehensive security assessments of IoT devices and their ecosystems by testing hardware interfaces, firmware, network communications, cloud APIs, and companion mobile applications. The tester uses firmware extraction and analysis, hardware debugging via UART and JTAG, network protocol an
- [[performing-android-app-static-analysis-with-mobsf]] *(similar)* — Performs automated static analysis of Android applications using Mobile Security Framework (MobSF) to identify hardcoded secrets, insecure permissions, vulnerable components, weak cryptography, and code-level security flaws without executing the application. Use when assessing Android APK/AAB files 
- [[performing-cryptographic-audit-of-application]] *(similar)* — A cryptographic audit systematically reviews an application's use of cryptographic primitives, protocols, and key management to identify vulnerabilities such as weak algorithms, insecure modes, hardco
- [[performing-ios-app-security-assessment]] *(similar)* — Performs comprehensive iOS application security assessments using Frida for dynamic instrumentation, Objection for runtime exploration, SSL pinning bypass for traffic interception, keychain extraction for credential analysis, and IPA static analysis for binary-level review. Use when conducting autho
- [[performing-ssl-tls-security-assessment]] *(similar)* — Assess SSL/TLS server configurations using the sslyze Python library to evaluate cipher suites, certificate chains, protocol versions, HSTS headers, and known vulnerabilities like Heartbleed and ROBOT.
- [[auditing-uefi-firmware-with-chipsec]] *(similar)* — Use Intel CHIPSEC to assess platform firmware configuration, SPI flash write protection, BIOS lock, SMM/SMRR, and Secure Boot variable state, dump SPI flash, and triage UEFI variables for firmware-level threats.
- [[performing-agentless-vulnerability-scanning]] *(similar)* — Configure and execute agentless vulnerability scanning using network protocols, cloud snapshot analysis, and API-based discovery to assess systems without installing endpoint agents.
- [[performing-authenticated-scan-with-openvas]] *(similar)* — Configure and execute authenticated vulnerability scans using OpenVAS/Greenbone Vulnerability Management with SSH and SMB credentials for comprehensive host-level assessment.
- [[performing-aws-account-enumeration-with-scout-suite]] *(similar)* — Perform comprehensive security posture assessment of AWS accounts using ScoutSuite to enumerate resources, identify misconfigurations, and generate actionable security reports.
- [[performing-ot-vulnerability-scanning-safely]] *(similar)* — Perform vulnerability scanning in OT/ICS environments safely using passive monitoring, native protocol queries, and carefully controlled active scanning with Tenable OT Security to identify vulnerabilities without disrupting industrial processes or crashing legacy controllers.

- [[performing-post-quantum-cryptography-migration]] *(similar)* — Assesses organizational readiness for post-quantum cryptography migration per NIST FIPS 203/204/205 standards. Performs cryptographic inventory scanning to identify quantum-vulnerable algorithms (RSA, ECDH, ECDSA), evaluates hybrid TLS configurations with X25519MLKEM768, and validates CRYSTALS-Kyber
- [[performing-scada-hmi-security-assessment]] *(similar)* — Perform security assessments of SCADA Human-Machine Interface (HMI) systems to identify vulnerabilities in web-based HMIs, thin-client configurations, authentication mechanisms, and communication channels between HMI and PLCs, aligned with IEC 62443 and NIST SP 800-82 guidelines.

- [[performing-security-headers-audit]] *(similar)* — Auditing HTTP security headers including CSP, HSTS, X-Frame-Options, and cookie attributes to identify missing or misconfigured browser-level protections.

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
