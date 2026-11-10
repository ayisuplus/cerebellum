---
title: auditing-aws-s3-bucket-permissions
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [auditing-cloud-with-cis-benchmarks, auditing-gcp-iam-permissions, auditing-terraform-infrastructure-for-security, implementing-rbac-hardening-for-kubernetes, performing-aws-account-enumeration-with-scout-suite, performing-aws-privilege-escalation-assessment, performing-privileged-account-access-review, performing-serverless-function-security-review, performing-service-account-audit, remediating-s3-bucket-misconfiguration]
confidence: medium
---

Systematically audit AWS S3 bucket permissions to identify publicly accessible buckets, overly permissive ACLs, misconfigured bucket policies, and missing encryption settings using AWS CLI, S3audit, and Prowler to enforce least-privilege data access controls.

## Metadata

- **ID:** `auditing-aws-s3-bucket-permissions`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/auditing-aws-s3-bucket-permissions/SKILL.md`
- **Score:** 52.0
- **Edges:** 10

## Related Skills

- [[auditing-terraform-infrastructure-for-security]] *(complement)* — Auditing Terraform infrastructure-as-code for security misconfigurations using Checkov, tfsec, Terrascan, and OPA/Rego policies to detect overly permissive IAM policies, public resource exposure, missing encryption, and insecure defaults before cloud deployment.

- [[remediating-s3-bucket-misconfiguration]] *(complement)* — This skill provides step-by-step procedures for identifying and remediating Amazon S3 bucket misconfigurations that expose sensitive data to unauthorized access. It covers enabling S3 Block Public Access at account and bucket levels, auditing bucket policies and ACLs, enforcing encryption, configuri
- [[auditing-cloud-with-cis-benchmarks]] *(similar)* — This skill details how to conduct cloud security audits using Center for Internet Security benchmarks for AWS, Azure, and GCP. It covers interpreting CIS Foundations Benchmark controls, running automated assessments with tools like Prowler and ScoutSuite, remediating failed controls, and maintaining
- [[auditing-gcp-iam-permissions]] *(similar)* — Auditing Google Cloud Platform IAM permissions to identify overly permissive bindings, primitive role usage, service account key proliferation, and cross-project access risks using gcloud CLI, Policy Analyzer, and IAM Recommender.

- [[performing-aws-account-enumeration-with-scout-suite]] *(similar)* — Perform comprehensive security posture assessment of AWS accounts using ScoutSuite to enumerate resources, identify misconfigurations, and generate actionable security reports.
- [[implementing-rbac-hardening-for-kubernetes]] *(similar)* — Harden Kubernetes Role-Based Access Control by implementing least-privilege policies, auditing role bindings, eliminating cluster-admin sprawl, and integrating external identity providers.
- [[performing-aws-privilege-escalation-assessment]] *(similar)* — Performing authorized privilege escalation assessments in AWS environments to identify IAM misconfigurations that allow users or roles to elevate their permissions using Pacu, CloudFox, Principal Mapper, and manual IAM policy analysis techniques.

- [[performing-privileged-account-access-review]] *(similar)* — Conduct systematic reviews of privileged accounts to validate access rights, identify excessive permissions, and enforce least privilege across PAM infrastructure.
- [[performing-serverless-function-security-review]] *(similar)* — Performing security reviews of serverless functions across AWS Lambda, Azure Functions, and GCP Cloud Functions to identify overly permissive execution roles, insecure environment variables, injection vulnerabilities, and missing runtime protections.

- [[performing-service-account-audit]] *(similar)* — Audit service accounts across enterprise infrastructure to identify orphaned, over-privileged, and non-compliant accounts. This skill covers discovery of service accounts in Active Directory, cloud pl

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
