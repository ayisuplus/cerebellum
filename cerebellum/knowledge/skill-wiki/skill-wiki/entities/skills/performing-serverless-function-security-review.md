---
title: performing-serverless-function-security-review
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [auditing-aws-s3-bucket-permissions, auditing-gcp-iam-permissions, auditing-terraform-infrastructure-for-security, implementing-rbac-hardening-for-kubernetes, implementing-zero-trust-in-cloud, performing-android-app-static-analysis-with-mobsf, performing-aws-account-enumeration-with-scout-suite, performing-aws-privilege-escalation-assessment, performing-cryptographic-audit-of-application, performing-kubernetes-etcd-security-assessment, performing-oauth-scope-minimization-review, performing-privileged-account-access-review, performing-security-headers-audit, performing-service-account-audit, performing-threat-modeling-with-owasp-threat-dragon, rails-security-review, testing-for-sensitive-data-exposure]
confidence: medium
---

Performing security reviews of serverless functions across AWS Lambda, Azure Functions, and GCP Cloud Functions to identify overly permissive execution roles, insecure environment variables, injection vulnerabilities, and missing runtime protections.

## Metadata

- **ID:** `performing-serverless-function-security-review`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/performing-serverless-function-security-review/SKILL.md`
- **Score:** 45.0
- **Edges:** 17

## Related Skills

- [[auditing-aws-s3-bucket-permissions]] *(similar)* — Systematically audit AWS S3 bucket permissions to identify publicly accessible buckets, overly permissive ACLs, misconfigured bucket policies, and missing encryption settings using AWS CLI, S3audit, and Prowler to enforce least-privilege data access controls.

- [[performing-android-app-static-analysis-with-mobsf]] *(similar)* — Performs automated static analysis of Android applications using Mobile Security Framework (MobSF) to identify hardcoded secrets, insecure permissions, vulnerable components, weak cryptography, and code-level security flaws without executing the application. Use when assessing Android APK/AAB files 
- [[performing-cryptographic-audit-of-application]] *(similar)* — A cryptographic audit systematically reviews an application's use of cryptographic primitives, protocols, and key management to identify vulnerabilities such as weak algorithms, insecure modes, hardco
- [[performing-service-account-audit]] *(similar)* — Audit service accounts across enterprise infrastructure to identify orphaned, over-privileged, and non-compliant accounts. This skill covers discovery of service accounts in Active Directory, cloud pl
- [[rails-security-review]] *(similar)* — Performs security audits and vulnerability assessments on Ruby on Rails application code. Use when reviewing Rails code for security risks, assessing authentication or authorization, auditing parameter handling, redirects, file uploads, secrets management, or checking for XSS, CSRF, SSRF, SQL inject
- [[auditing-gcp-iam-permissions]] *(similar)* — Auditing Google Cloud Platform IAM permissions to identify overly permissive bindings, primitive role usage, service account key proliferation, and cross-project access risks using gcloud CLI, Policy Analyzer, and IAM Recommender.

- [[auditing-terraform-infrastructure-for-security]] *(similar)* — Auditing Terraform infrastructure-as-code for security misconfigurations using Checkov, tfsec, Terrascan, and OPA/Rego policies to detect overly permissive IAM policies, public resource exposure, missing encryption, and insecure defaults before cloud deployment.

- [[implementing-rbac-hardening-for-kubernetes]] *(similar)* — Harden Kubernetes Role-Based Access Control by implementing least-privilege policies, auditing role bindings, eliminating cluster-admin sprawl, and integrating external identity providers.
- [[implementing-zero-trust-in-cloud]] *(similar)* — This skill guides organizations through implementing zero trust architecture in cloud environments following NIST SP 800-207 and Google BeyondCorp principles. It covers identity-centric access controls, micro-segmentation, continuous verification, device trust assessment, and deploying Identity-Awar
- [[performing-aws-account-enumeration-with-scout-suite]] *(similar)* — Perform comprehensive security posture assessment of AWS accounts using ScoutSuite to enumerate resources, identify misconfigurations, and generate actionable security reports.
- [[performing-aws-privilege-escalation-assessment]] *(similar)* — Performing authorized privilege escalation assessments in AWS environments to identify IAM misconfigurations that allow users or roles to elevate their permissions using Pacu, CloudFox, Principal Mapper, and manual IAM policy analysis techniques.

- [[performing-kubernetes-etcd-security-assessment]] *(similar)* — Assess the security posture of Kubernetes etcd clusters by evaluating encryption at rest, TLS configuration, access controls, backup encryption, and network isolation.
- [[performing-oauth-scope-minimization-review]] *(similar)* — Performs OAuth 2.0 scope minimization review to identify over-permissioned third-party application integrations, excessive API scopes, unused token grants, and risky OAuth consent patterns across identity providers and SaaS platforms. Activates for requests involving OAuth scope audit, API permissio
- [[performing-privileged-account-access-review]] *(similar)* — Conduct systematic reviews of privileged accounts to validate access rights, identify excessive permissions, and enforce least privilege across PAM infrastructure.
- [[performing-security-headers-audit]] *(similar)* — Auditing HTTP security headers including CSP, HSTS, X-Frame-Options, and cookie attributes to identify missing or misconfigured browser-level protections.
- [[performing-threat-modeling-with-owasp-threat-dragon]] *(similar)* — Use OWASP Threat Dragon to create data flow diagrams, identify threats using STRIDE and LINDDUN methodologies, and generate threat model reports for secure design review.
- [[testing-for-sensitive-data-exposure]] *(similar)* — Identifying sensitive data exposure vulnerabilities including API key leakage, PII in responses, insecure storage, and unprotected data transmission during security assessments.

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
