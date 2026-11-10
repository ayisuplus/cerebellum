---
title: auditing-terraform-infrastructure-for-security
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [auditing-aws-s3-bucket-permissions, auditing-azure-active-directory-configuration, auditing-cloud-with-cis-benchmarks, auditing-foundry-smart-contract-security, auditing-gcp-iam-permissions, auditing-mcp-servers-for-tool-poisoning, building-vulnerability-scanning-workflow, implementing-api-security-testing-with-42crunch, implementing-rbac-hardening-for-kubernetes, performing-aws-account-enumeration-with-scout-suite, performing-aws-privilege-escalation-assessment, performing-docker-bench-security-assessment, performing-serverless-function-security-review, performing-service-account-audit, rails-security-review, remediating-s3-bucket-misconfiguration, terraform-style-guide]
confidence: medium
---

Auditing Terraform infrastructure-as-code for security misconfigurations using Checkov, tfsec, Terrascan, and OPA/Rego policies to detect overly permissive IAM policies, public resource exposure, missing encryption, and insecure defaults before cloud deployment.

## Metadata

- **ID:** `auditing-terraform-infrastructure-for-security`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/auditing-terraform-infrastructure-for-security/SKILL.md`
- **Score:** 48.0
- **Edges:** 17

## Related Skills

- [[implementing-rbac-hardening-for-kubernetes]] *(similar)* — Harden Kubernetes Role-Based Access Control by implementing least-privilege policies, auditing role bindings, eliminating cluster-admin sprawl, and integrating external identity providers.
- [[performing-aws-account-enumeration-with-scout-suite]] *(similar)* — Perform comprehensive security posture assessment of AWS accounts using ScoutSuite to enumerate resources, identify misconfigurations, and generate actionable security reports.
- [[performing-aws-privilege-escalation-assessment]] *(similar)* — Performing authorized privilege escalation assessments in AWS environments to identify IAM misconfigurations that allow users or roles to elevate their permissions using Pacu, CloudFox, Principal Mapper, and manual IAM policy analysis techniques.

- [[performing-serverless-function-security-review]] *(similar)* — Performing security reviews of serverless functions across AWS Lambda, Azure Functions, and GCP Cloud Functions to identify overly permissive execution roles, insecure environment variables, injection vulnerabilities, and missing runtime protections.

- [[terraform-style-guide]] *(similar)* — Generate Terraform HCL code following HashiCorp's official style conventions and best practices. Use when writing, reviewing, or generating Terraform configurations.
- [[auditing-aws-s3-bucket-permissions]] *(complement)* — Systematically audit AWS S3 bucket permissions to identify publicly accessible buckets, overly permissive ACLs, misconfigured bucket policies, and missing encryption settings using AWS CLI, S3audit, and Prowler to enforce least-privilege data access controls.

- [[auditing-azure-active-directory-configuration]] *(similar)* — Auditing Microsoft Entra ID (Azure Active Directory) configuration to identify risky authentication policies, overly permissive role assignments, stale accounts, conditional access gaps, and guest user risks using AzureAD PowerShell, Microsoft Graph API, and ScoutSuite.

- [[auditing-cloud-with-cis-benchmarks]] *(similar)* — This skill details how to conduct cloud security audits using Center for Internet Security benchmarks for AWS, Azure, and GCP. It covers interpreting CIS Foundations Benchmark controls, running automated assessments with tools like Prowler and ScoutSuite, remediating failed controls, and maintaining
- [[auditing-foundry-smart-contract-security]] *(similar)* — Pre-deployment security audit of Solidity smart contracts in a Foundry project. Combines static analysis (Slither, Aderyn), symbolic execution (Mythril), and property-based testing (forge fuzz + invariant tests with handlers) to catch reentrancy, access-control, oracle/price manipulation, and arithm
- [[auditing-gcp-iam-permissions]] *(similar)* — Auditing Google Cloud Platform IAM permissions to identify overly permissive bindings, primitive role usage, service account key proliferation, and cross-project access risks using gcloud CLI, Policy Analyzer, and IAM Recommender.

- [[auditing-mcp-servers-for-tool-poisoning]] *(similar)* — Scan Model Context Protocol servers and tool metadata for poisoning, SSRF, and unauthenticated exposure.
- [[building-vulnerability-scanning-workflow]] *(similar)* — Builds a structured vulnerability scanning workflow using tools like Nessus, Qualys, and OpenVAS to discover, prioritize, and track remediation of security vulnerabilities across infrastructure. Use when SOC teams need to establish recurring vulnerability assessment processes, integrate scan results
- [[implementing-api-security-testing-with-42crunch]] *(similar)* — Implement comprehensive API security testing using the 42Crunch platform to perform static audit and dynamic conformance scanning of OpenAPI specifications.
- [[performing-docker-bench-security-assessment]] *(similar)* — Docker Bench for Security is an open-source script that checks dozens of common best practices around deploying Docker containers in production. Based on the CIS Docker Benchmark, it audits host confi
- [[performing-service-account-audit]] *(similar)* — Audit service accounts across enterprise infrastructure to identify orphaned, over-privileged, and non-compliant accounts. This skill covers discovery of service accounts in Active Directory, cloud pl
- [[rails-security-review]] *(similar)* — Performs security audits and vulnerability assessments on Ruby on Rails application code. Use when reviewing Rails code for security risks, assessing authentication or authorization, auditing parameter handling, redirects, file uploads, secrets management, or checking for XSS, CSRF, SSRF, SQL inject
- [[remediating-s3-bucket-misconfiguration]] *(similar)* — This skill provides step-by-step procedures for identifying and remediating Amazon S3 bucket misconfigurations that expose sensitive data to unauthorized access. It covers enabling S3 Block Public Access at account and bucket levels, auditing bucket policies and ACLs, enforcing encryption, configuri

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
