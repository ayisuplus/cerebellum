---
title: performing-privileged-account-access-review
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [auditing-aws-s3-bucket-permissions, auditing-gcp-iam-permissions, implementing-azure-ad-privileged-identity-management, implementing-pam-for-database-access, implementing-rbac-hardening-for-kubernetes, performing-access-review-and-certification, performing-aws-account-enumeration-with-scout-suite, performing-aws-privilege-escalation-assessment, performing-entitlement-review-with-sailpoint-iiq, performing-oauth-scope-minimization-review, performing-serverless-function-security-review, performing-service-account-audit]
confidence: low
---

Conduct systematic reviews of privileged accounts to validate access rights, identify excessive permissions, and enforce least privilege across PAM infrastructure.

## Metadata

- **ID:** `performing-privileged-account-access-review`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/performing-privileged-account-access-review/SKILL.md`
- **Score:** 38.0
- **Edges:** 12

## Related Skills

- [[auditing-aws-s3-bucket-permissions]] *(similar)* — Systematically audit AWS S3 bucket permissions to identify publicly accessible buckets, overly permissive ACLs, misconfigured bucket policies, and missing encryption settings using AWS CLI, S3audit, and Prowler to enforce least-privilege data access controls.

- [[auditing-gcp-iam-permissions]] *(similar)* — Auditing Google Cloud Platform IAM permissions to identify overly permissive bindings, primitive role usage, service account key proliferation, and cross-project access risks using gcloud CLI, Policy Analyzer, and IAM Recommender.

- [[performing-aws-account-enumeration-with-scout-suite]] *(similar)* — Perform comprehensive security posture assessment of AWS accounts using ScoutSuite to enumerate resources, identify misconfigurations, and generate actionable security reports.
- [[performing-serverless-function-security-review]] *(similar)* — Performing security reviews of serverless functions across AWS Lambda, Azure Functions, and GCP Cloud Functions to identify overly permissive execution roles, insecure environment variables, injection vulnerabilities, and missing runtime protections.

- [[performing-service-account-audit]] *(similar)* — Audit service accounts across enterprise infrastructure to identify orphaned, over-privileged, and non-compliant accounts. This skill covers discovery of service accounts in Active Directory, cloud pl
- [[performing-access-review-and-certification]] *(complement)* — Conduct systematic access reviews and certifications to ensure users have appropriate access rights aligned with their roles. This skill covers review campaign design, reviewer selection, risk-based p
- [[implementing-azure-ad-privileged-identity-management]] *(similar)* — Configure Microsoft Entra Privileged Identity Management to enforce just-in-time role activation, approval workflows, and access reviews for Azure AD privileged roles.
- [[implementing-pam-for-database-access]] *(similar)* — Deploy privileged access management for database systems including Oracle, SQL Server, PostgreSQL, and MySQL. Covers session proxy configuration, credential vaulting, query auditing, dynamic credentia
- [[implementing-rbac-hardening-for-kubernetes]] *(similar)* — Harden Kubernetes Role-Based Access Control by implementing least-privilege policies, auditing role bindings, eliminating cluster-admin sprawl, and integrating external identity providers.
- [[performing-aws-privilege-escalation-assessment]] *(similar)* — Performing authorized privilege escalation assessments in AWS environments to identify IAM misconfigurations that allow users or roles to elevate their permissions using Pacu, CloudFox, Principal Mapper, and manual IAM policy analysis techniques.

- [[performing-entitlement-review-with-sailpoint-iiq]] *(similar)* — Performs entitlement review and access certification campaigns using SailPoint IdentityIQ including manager certifications, targeted entitlement reviews, role-based access validation, SOD violation remediation, and automated revocation workflows. Activates for requests involving access reviews, enti
- [[performing-oauth-scope-minimization-review]] *(similar)* — Performs OAuth 2.0 scope minimization review to identify over-permissioned third-party application integrations, excessive API scopes, unused token grants, and risky OAuth consent patterns across identity providers and SaaS platforms. Activates for requests involving OAuth scope audit, API permissio

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
