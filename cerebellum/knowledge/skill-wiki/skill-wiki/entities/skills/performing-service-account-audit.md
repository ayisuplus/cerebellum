---
title: performing-service-account-audit
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [auditing-aws-s3-bucket-permissions, auditing-azure-active-directory-configuration, auditing-cloud-with-cis-benchmarks, auditing-gcp-iam-permissions, auditing-terraform-infrastructure-for-security, implementing-zero-trust-in-cloud, performing-access-review-and-certification, performing-agentless-vulnerability-scanning, performing-aws-account-enumeration-with-scout-suite, performing-aws-privilege-escalation-assessment, performing-entitlement-review-with-sailpoint-iiq, performing-oauth-scope-minimization-review, performing-ot-vulnerability-assessment-with-claroty, performing-power-grid-cybersecurity-assessment, performing-privileged-account-access-review, performing-serverless-function-security-review, performing-soc2-type2-audit-preparation]
confidence: low
---

Audit service accounts across enterprise infrastructure to identify orphaned, over-privileged, and non-compliant accounts. This skill covers discovery of service accounts in Active Directory, cloud pl

## Metadata

- **ID:** `performing-service-account-audit`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/performing-service-account-audit/SKILL.md`
- **Score:** 35.0
- **Edges:** 17

## Related Skills

- [[auditing-aws-s3-bucket-permissions]] *(similar)* — Systematically audit AWS S3 bucket permissions to identify publicly accessible buckets, overly permissive ACLs, misconfigured bucket policies, and missing encryption settings using AWS CLI, S3audit, and Prowler to enforce least-privilege data access controls.

- [[auditing-terraform-infrastructure-for-security]] *(similar)* — Auditing Terraform infrastructure-as-code for security misconfigurations using Checkov, tfsec, Terrascan, and OPA/Rego policies to detect overly permissive IAM policies, public resource exposure, missing encryption, and insecure defaults before cloud deployment.

- [[performing-agentless-vulnerability-scanning]] *(similar)* — Configure and execute agentless vulnerability scanning using network protocols, cloud snapshot analysis, and API-based discovery to assess systems without installing endpoint agents.
- [[performing-ot-vulnerability-assessment-with-claroty]] *(similar)* — This skill covers performing vulnerability assessments in OT environments using the Claroty xDome platform for comprehensive asset discovery, risk scoring, vulnerability correlation, and remediation prioritization. It addresses passive vulnerability identification through traffic analysis, active sa
- [[performing-soc2-type2-audit-preparation]] *(similar)* — Automates SOC 2 Type II audit preparation including gap assessment against AICPA Trust Services Criteria (CC1-CC9), evidence collection from cloud providers and identity systems, control testing validation, remediation tracking, and continuous compliance monitoring. Covers all five TSC categories (S
- [[auditing-azure-active-directory-configuration]] *(similar)* — Auditing Microsoft Entra ID (Azure Active Directory) configuration to identify risky authentication policies, overly permissive role assignments, stale accounts, conditional access gaps, and guest user risks using AzureAD PowerShell, Microsoft Graph API, and ScoutSuite.

- [[auditing-cloud-with-cis-benchmarks]] *(similar)* — This skill details how to conduct cloud security audits using Center for Internet Security benchmarks for AWS, Azure, and GCP. It covers interpreting CIS Foundations Benchmark controls, running automated assessments with tools like Prowler and ScoutSuite, remediating failed controls, and maintaining
- [[auditing-gcp-iam-permissions]] *(similar)* — Auditing Google Cloud Platform IAM permissions to identify overly permissive bindings, primitive role usage, service account key proliferation, and cross-project access risks using gcloud CLI, Policy Analyzer, and IAM Recommender.

- [[implementing-zero-trust-in-cloud]] *(similar)* — This skill guides organizations through implementing zero trust architecture in cloud environments following NIST SP 800-207 and Google BeyondCorp principles. It covers identity-centric access controls, micro-segmentation, continuous verification, device trust assessment, and deploying Identity-Awar
- [[performing-access-review-and-certification]] *(similar)* — Conduct systematic access reviews and certifications to ensure users have appropriate access rights aligned with their roles. This skill covers review campaign design, reviewer selection, risk-based p
- [[performing-aws-account-enumeration-with-scout-suite]] *(similar)* — Perform comprehensive security posture assessment of AWS accounts using ScoutSuite to enumerate resources, identify misconfigurations, and generate actionable security reports.
- [[performing-aws-privilege-escalation-assessment]] *(similar)* — Performing authorized privilege escalation assessments in AWS environments to identify IAM misconfigurations that allow users or roles to elevate their permissions using Pacu, CloudFox, Principal Mapper, and manual IAM policy analysis techniques.

- [[performing-entitlement-review-with-sailpoint-iiq]] *(similar)* — Performs entitlement review and access certification campaigns using SailPoint IdentityIQ including manager certifications, targeted entitlement reviews, role-based access validation, SOD violation remediation, and automated revocation workflows. Activates for requests involving access reviews, enti
- [[performing-oauth-scope-minimization-review]] *(similar)* — Performs OAuth 2.0 scope minimization review to identify over-permissioned third-party application integrations, excessive API scopes, unused token grants, and risky OAuth consent patterns across identity providers and SaaS platforms. Activates for requests involving OAuth scope audit, API permissio
- [[performing-power-grid-cybersecurity-assessment]] *(similar)* — This skill covers conducting cybersecurity assessments of electric power grid infrastructure including generation facilities, transmission substations, distribution systems, and energy management system (EMS) control centers. It addresses NERC CIP compliance verification, substation automation secur
- [[performing-privileged-account-access-review]] *(similar)* — Conduct systematic reviews of privileged accounts to validate access rights, identify excessive permissions, and enforce least privilege across PAM infrastructure.
- [[performing-serverless-function-security-review]] *(similar)* — Performing security reviews of serverless functions across AWS Lambda, Azure Functions, and GCP Cloud Functions to identify overly permissive execution roles, insecure environment variables, injection vulnerabilities, and missing runtime protections.


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
