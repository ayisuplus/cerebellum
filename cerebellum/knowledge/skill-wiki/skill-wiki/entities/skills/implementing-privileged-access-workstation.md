---
title: implementing-privileged-access-workstation
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [configuring-active-directory-tiered-model, hardening-docker-containers-for-production, hardening-linux-endpoint-with-cis-benchmark, implementing-aws-nitro-enclave-security, implementing-cisa-zero-trust-maturity-model, implementing-conditional-access-policies-azure-ad, implementing-conduit-security-for-ot-remote-access, implementing-disk-encryption-with-bitlocker, implementing-google-workspace-admin-security, implementing-identity-verification-for-zero-trust, implementing-zero-standing-privilege-with-cyberark, implementing-zero-trust-for-saas-applications, performing-hardware-security-module-integration, securing-aws-iam-permissions, securing-remote-access-to-ot-environment]
confidence: low
---

Design and implement Privileged Access Workstations (PAWs) with device hardening, just-in-time access, and integration with CyberArk or BeyondTrust for secure administrative operations.

## Metadata

- **ID:** `implementing-privileged-access-workstation`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/implementing-privileged-access-workstation/SKILL.md`
- **Score:** 27.0
- **Edges:** 15

## Related Skills

- [[implementing-zero-standing-privilege-with-cyberark]] *(complement)* — Deploy CyberArk Secure Cloud Access to eliminate standing privileges in hybrid and multi-cloud environments using just-in-time access with time, entitlement, and approval controls.
- [[implementing-cisa-zero-trust-maturity-model]] *(similar)* — Implement the CISA Zero Trust Maturity Model v2.0 across the five pillars of identity, devices, networks, applications, and data to achieve progressive organizational zero trust maturity.
- [[implementing-zero-trust-for-saas-applications]] *(similar)* — Implementing zero trust access controls for SaaS applications using CASB, SSPM, conditional access policies, OAuth app governance, and session controls to enforce identity verification, device compliance, and data protection for cloud-hosted services.

- [[securing-aws-iam-permissions]] *(similar)* — This skill guides practitioners through hardening AWS Identity and Access Management configurations to enforce least privilege access across cloud accounts. It covers IAM policy scoping, permission boundaries, Access Analyzer integration, and credential rotation strategies to reduce the blast radius
- [[securing-remote-access-to-ot-environment]] *(similar)* — This skill covers implementing secure remote access to OT/ICS environments for operators, engineers, and vendors while preventing unauthorized access that could compromise industrial operations. It addresses jump server architecture, multi-factor authentication, session recording, privileged access 
- [[configuring-active-directory-tiered-model]] *(similar)* — Implement Microsoft's Enhanced Security Admin Environment (ESAE) tiered administration model for Active Directory. Covers Tier 0/1/2 separation, privileged access workstations (PAWs), administrative f
- [[hardening-docker-containers-for-production]] *(similar)* — Hardening Docker containers for production involves applying security best practices aligned with CIS Docker Benchmark v1.8.0 to minimize attack surface, prevent privilege escalation, and enforce leas
- [[hardening-linux-endpoint-with-cis-benchmark]] *(similar)* — Hardens Linux endpoints using CIS Benchmark recommendations for Ubuntu, RHEL, and CentOS to reduce attack surface, enforce security baselines, and meet compliance requirements. Use when deploying new Linux servers, remediating audit findings, or establishing security baselines for Linux infrastructu
- [[implementing-aws-nitro-enclave-security]] *(similar)* — Implements AWS Nitro Enclave-based confidential computing environments with cryptographic attestation, KMS policy integration using PCR-based condition keys, and secure vsock communication channels. The practitioner builds enclave images, configures attestation-aware KMS policies, validates attestat
- [[implementing-conditional-access-policies-azure-ad]] *(similar)* — Configure Microsoft Entra ID (Azure AD) Conditional Access policies for zero trust access control. Covers signal-based policy design, device compliance requirements, risk-based authentication, named l
- [[implementing-conduit-security-for-ot-remote-access]] *(similar)* — Implement secure conduit architecture for OT remote access following IEC 62443 zones and conduits model, deploying jump servers, MFA-enabled gateways, session recording, and approval-based workflows to control vendor and engineer access to industrial control systems without exposing OT networks dire
- [[implementing-disk-encryption-with-bitlocker]] *(similar)* — Implements full disk encryption using Microsoft BitLocker on Windows endpoints to protect data at rest from unauthorized access in case of device loss or theft. Use when deploying encryption for compliance requirements, securing mobile workstations, or implementing data protection controls across th
- [[implementing-google-workspace-admin-security]] *(similar)* — Implements comprehensive Google Workspace security hardening including admin console configuration, phishing-resistant MFA enforcement, DLP policies, email authentication (SPF/DKIM/DMARC), OAuth app control, and external sharing restrictions. Activates for requests involving Google Workspace hardeni
- [[implementing-identity-verification-for-zero-trust]] *(similar)* — Implement continuous identity verification for zero trust using phishing-resistant MFA (FIDO2/WebAuthn), risk-based conditional access, and identity governance aligned with the CISA Zero Trust Maturity Model.
- [[performing-hardware-security-module-integration]] *(similar)* — Integrate Hardware Security Modules (HSMs) using PKCS#11 interface for cryptographic key management, signing operations, and secure key storage with python-pkcs11, AWS CloudHSM, and YubiHSM2.

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
