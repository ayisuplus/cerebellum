---
title: securing-kubernetes-on-cloud
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-kubernetes-audit-logs, detecting-cloud-threats-with-guardduty, detecting-privilege-escalation-in-kubernetes-pods, implementing-cloud-security-posture-management, implementing-infrastructure-as-code-security-scanning, implementing-privileged-access-management-with-cyberark, implementing-secret-scanning-with-gitleaks, implementing-security-monitoring-with-datadog, implementing-sigstore-for-software-signing]
confidence: medium
---

This skill covers hardening managed Kubernetes clusters on EKS, AKS, and GKE by implementing Pod Security Standards, network policies, workload identity, RBAC scoping, image admission controls, and runtime security monitoring. It addresses cloud-specific security features including IRSA for EKS, Wor

## Metadata

- **ID:** `securing-kubernetes-on-cloud`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/securing-kubernetes-on-cloud/SKILL.md`
- **Score:** 42.0
- **Edges:** 9

## Related Skills

- [[analyzing-kubernetes-audit-logs]] *(similar)* — Parses Kubernetes API server audit logs (JSON lines) to detect exec-into-pod, secret access, RBAC modifications, privileged pod creation, and anonymous API access. Builds threat detection rules from audit event patterns. Use when investigating Kubernetes cluster compromise or building k8s-specific S
- [[detecting-cloud-threats-with-guardduty]] *(similar)* — This skill teaches security teams how to deploy and operationalize Amazon GuardDuty for continuous threat detection across AWS accounts and workloads. It covers enabling protection plans for S3, EKS, EC2 runtime monitoring, and Lambda, interpreting finding severity levels, and building automated res
- [[implementing-cloud-security-posture-management]] *(similar)* — Implementing Cloud Security Posture Management (CSPM) to continuously monitor multi-cloud environments for misconfigurations, compliance violations, and security risks using Prowler, ScoutSuite, AWS Security Hub, Azure Defender, and GCP Security Command Center.

- [[implementing-secret-scanning-with-gitleaks]] *(similar)* — This skill covers implementing Gitleaks for detecting and preventing hardcoded secrets in git repositories. It addresses configuring pre-commit hooks, CI/CD pipeline integration, custom rule authoring for organization-specific secrets, baseline management for existing repositories, and remediation w
- [[implementing-security-monitoring-with-datadog]] *(similar)* — Implements security monitoring using Datadog Cloud SIEM, Cloud Security Management (CSM), and Workload Protection to detect threats, enforce compliance, and respond to security events across cloud and hybrid infrastructure. Covers Agent deployment, log source ingestion, detection rule creation, secu
- [[detecting-privilege-escalation-in-kubernetes-pods]] *(similar)* — Detect and prevent privilege escalation in Kubernetes pods by monitoring security contexts, capabilities, and syscall patterns with Falco and OPA policies.
- [[implementing-infrastructure-as-code-security-scanning]] *(similar)* — This skill covers implementing automated security scanning for Infrastructure as Code (IaC) templates using tools like Checkov, tfsec, and KICS. It addresses detecting misconfigurations in Terraform, CloudFormation, Kubernetes manifests, and Helm charts before deployment, establishing policy-based g
- [[implementing-privileged-access-management-with-cyberark]] *(similar)* — Deploy CyberArk Privileged Access Management to discover, vault, rotate, and monitor privileged credentials across enterprise infrastructure. This skill covers vault architecture, session isolation, c
- [[implementing-sigstore-for-software-signing]] *(similar)* — Implements Sigstore-based software signing and verification using Cosign keyless signing, Rekor transparency log verification, and Fulcio certificate authority integration to establish cryptographic provenance for container images, binaries, and software artifacts. The practitioner configures OIDC-b

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
