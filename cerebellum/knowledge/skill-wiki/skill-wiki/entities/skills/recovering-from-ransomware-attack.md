---
title: recovering-from-ransomware-attack
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [building-incident-response-playbook, building-soc-playbook-for-ransomware, conducting-cloud-incident-response, conducting-malware-incident-response, implementing-immutable-backup-with-restic, implementing-ot-incident-response-playbook, implementing-ransomware-backup-strategy, performing-cloud-incident-containment-procedures, performing-ransomware-response, performing-ransomware-tabletop-exercise, validating-backup-integrity-for-recovery]
confidence: medium
---

Executes structured recovery from a ransomware incident following NIST and CISA frameworks, including environment isolation, forensic evidence preservation, clean infrastructure rebuild, prioritized system restoration from verified backups, credential reset, and validation against re-infection. Cove

## Metadata

- **ID:** `recovering-from-ransomware-attack`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/recovering-from-ransomware-attack/SKILL.md`
- **Score:** 55.0
- **Edges:** 11

## Related Skills

- [[building-incident-response-playbook]] *(similar)* — Designs and documents structured incident response playbooks that define step-by-step procedures for specific incident types aligned with NIST SP 800-61r3 and SANS PICERL frameworks. Covers playbook structure, decision trees, escalation criteria, RACI matrices, and integration with SOAR platforms. A
- [[conducting-cloud-incident-response]] *(similar)* — Responds to security incidents in cloud environments (AWS, Azure, GCP) by performing identity-based containment, cloud-native log analysis, resource isolation, and forensic evidence acquisition adapted for ephemeral cloud infrastructure. Activates for requests involving cloud incident response, AWS 
- [[conducting-malware-incident-response]] *(similar)* — Responds to malware infections across enterprise endpoints by identifying the malware family, determining infection vectors, assessing spread, and executing eradication procedures. Covers the full lifecycle from detection through containment, analysis, removal, and recovery. Activates for requests i
- [[implementing-ot-incident-response-playbook]] *(similar)* — Develop and implement OT-specific incident response playbooks aligned with SANS PICERL framework, IEC 62443, and NIST SP 800-82 that address unique ICS challenges including safety-critical systems, limited downtime tolerance, and coordination between IT SOC, OT engineering, and plant operations team
- [[validating-backup-integrity-for-recovery]] *(similar)* — Validate backup integrity through cryptographic hash verification, automated restore testing, corruption detection, and recoverability checks to ensure backups are reliable for disaster recovery and ransomware response scenarios.
- [[building-soc-playbook-for-ransomware]] *(similar)* — Builds a structured SOC incident response playbook for ransomware attacks covering detection, containment, eradication, and recovery phases with specific SIEM queries, isolation procedures, and decision trees. Use when SOC teams need formalized response procedures for ransomware incidents aligned to
- [[implementing-immutable-backup-with-restic]] *(similar)* — Implements immutable backup strategy using restic with S3-compatible storage and object lock for ransomware-resistant data protection. Automates backup creation, integrity verification via restic check --read-data, snapshot retention policy enforcement, and restore testing. Integrates with AWS S3 Ob
- [[implementing-ransomware-backup-strategy]] *(similar)* — Designs and implements a ransomware-resilient backup strategy following the 3-2-1-1-0 methodology (3 copies, 2 media types, 1 offsite, 1 immutable/air-gapped, 0 errors on restore verification). Configures backup schedules aligned to RPO/RTO requirements, implements backup credential isolation to pre
- [[performing-cloud-incident-containment-procedures]] *(similar)* — Execute cloud-native incident containment across AWS, Azure, and GCP by isolating compromised resources, revoking credentials, preserving forensic evidence, and applying security group restrictions to prevent lateral movement.
- [[performing-ransomware-response]] *(similar)* — Executes a structured ransomware incident response from initial detection through containment, forensic analysis, decryption assessment, recovery, and post-incident hardening. Addresses ransom negotiation considerations, backup integrity verification, and regulatory notification requirements. Activa
- [[performing-ransomware-tabletop-exercise]] *(similar)* — Plans and facilitates tabletop exercises simulating ransomware incidents to test organizational readiness, decision-making, and communication procedures. Designs realistic scenarios based on current ransomware threat actors (LockBit, ALPHV/BlackCat, Cl0p), injects covering double extortion, backup d

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
