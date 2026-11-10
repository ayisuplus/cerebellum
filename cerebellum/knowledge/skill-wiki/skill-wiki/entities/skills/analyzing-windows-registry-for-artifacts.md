---
title: analyzing-windows-registry-for-artifacts
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-slack-space-and-file-system-artifacts, analyzing-usb-device-connection-history, analyzing-windows-amcache-artifacts, analyzing-windows-lnk-files-for-artifacts, analyzing-windows-shellbag-artifacts, parsing-artifacts-with-eric-zimmerman-tools]
confidence: low
---

Extract and analyze Windows Registry hives to uncover user activity, installed software, autostart entries, and evidence of system compromise.

## Metadata

- **ID:** `analyzing-windows-registry-for-artifacts`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/analyzing-windows-registry-for-artifacts/SKILL.md`
- **Score:** 35.0
- **Edges:** 6

## Related Skills

- [[analyzing-usb-device-connection-history]] *(bridge)* — Investigate USB device connection history from Windows registry, event logs, and setupapi logs to track removable media usage and potential data exfiltration.
- [[analyzing-windows-amcache-artifacts]] *(bridge)* — Parses and analyzes the Windows Amcache.hve registry hive to extract evidence of program execution, application installation, and driver loading for digital forensics investigations. Uses Eric Zimmerman's AmcacheParser and Timeline Explorer for artifact extraction, SHA-1 hash correlation with threat
- [[analyzing-windows-lnk-files-for-artifacts]] *(bridge)* — Parse Windows LNK shortcut files to extract target paths, timestamps, volume information, and machine identifiers for forensic timeline reconstruction.
- [[analyzing-windows-shellbag-artifacts]] *(bridge)* — Analyze Windows Shellbag registry artifacts to reconstruct folder browsing activity, detect access to removable media and network shares, and establish user interaction with directories even after deletion using SBECmd and ShellBags Explorer.
- [[parsing-artifacts-with-eric-zimmerman-tools]] *(similar)* — Parse registry, prefetch, shellbags, and MFT with EZ Tools and Timeline Explorer.
- [[analyzing-slack-space-and-file-system-artifacts]] *(similar)* — Examine file system slack space, MFT entries, USN journal, and alternate data streams to recover hidden data and reconstruct file activity on NTFS volumes.

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
