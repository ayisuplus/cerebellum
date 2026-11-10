---
title: rails-security-review
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [packages]
category: packages
related: [auditing-foundry-smart-contract-security, auditing-terraform-infrastructure-for-security, performing-android-app-static-analysis-with-mobsf, performing-aws-account-enumeration-with-scout-suite, performing-cryptographic-audit-of-application, performing-docker-bench-security-assessment, performing-ios-app-security-assessment, performing-oauth-scope-minimization-review, performing-security-headers-audit, performing-serverless-function-security-review, performing-ssl-tls-security-assessment, rails-code-review, rails-migration-safety, rspec-best-practices, ruby, ruby-on-rails-best-practices, testing-api-security-with-owasp-top-10, testing-mobile-api-authentication]
confidence: medium
---

Performs security audits and vulnerability assessments on Ruby on Rails application code. Use when reviewing Rails code for security risks, assessing authentication or authorization, auditing parameter handling, redirects, file uploads, secrets management, or checking for XSS, CSRF, SSRF, SQL inject

## Metadata

- **ID:** `rails-security-review`
- **Source:** `autoskills/packages/autoskills/skills-registry/rails-security-review/SKILL.md`
- **Score:** 48.0
- **Edges:** 18

## Related Skills

- [[auditing-terraform-infrastructure-for-security]] *(similar)* — Auditing Terraform infrastructure-as-code for security misconfigurations using Checkov, tfsec, Terrascan, and OPA/Rego policies to detect overly permissive IAM policies, public resource exposure, missing encryption, and insecure defaults before cloud deployment.

- [[performing-aws-account-enumeration-with-scout-suite]] *(similar)* — Perform comprehensive security posture assessment of AWS accounts using ScoutSuite to enumerate resources, identify misconfigurations, and generate actionable security reports.
- [[performing-oauth-scope-minimization-review]] *(similar)* — Performs OAuth 2.0 scope minimization review to identify over-permissioned third-party application integrations, excessive API scopes, unused token grants, and risky OAuth consent patterns across identity providers and SaaS platforms. Activates for requests involving OAuth scope audit, API permissio
- [[rspec-best-practices]] *(similar)* — Use when writing, reviewing, or cleaning up RSpec tests for Ruby and Rails codebases. Covers spec type selection, factory design, flaky test fixes, shared examples, deterministic assertions, test-driven development discipline, and choosing the best first failing spec for Rails changes. Also applies 
- [[ruby-on-rails-best-practices]] *(similar)* — Ruby on Rails architecture and coding patterns from Basecamp. Use when writing, reviewing, or refactoring Rails code to follow proven conventions for models, controllers, jobs, and concerns. Triggers on tasks involving Rails models, concerns, controllers, background jobs, or Turbo/Hotwire.
- [[rails-code-review]] *(complement)* — Reviews Rails pull requests, focusing on controller/model conventions, migration safety, query performance, and Rails Way compliance. Covers routing, ActiveRecord, security, caching, and background jobs. Use when reviewing existing Rails code for quality, conducting a PR review, or doing a code revi
- [[auditing-foundry-smart-contract-security]] *(similar)* — Pre-deployment security audit of Solidity smart contracts in a Foundry project. Combines static analysis (Slither, Aderyn), symbolic execution (Mythril), and property-based testing (forge fuzz + invariant tests with handlers) to catch reentrancy, access-control, oracle/price manipulation, and arithm
- [[performing-android-app-static-analysis-with-mobsf]] *(similar)* — Performs automated static analysis of Android applications using Mobile Security Framework (MobSF) to identify hardcoded secrets, insecure permissions, vulnerable components, weak cryptography, and code-level security flaws without executing the application. Use when assessing Android APK/AAB files 
- [[performing-cryptographic-audit-of-application]] *(similar)* — A cryptographic audit systematically reviews an application's use of cryptographic primitives, protocols, and key management to identify vulnerabilities such as weak algorithms, insecure modes, hardco
- [[performing-docker-bench-security-assessment]] *(similar)* — Docker Bench for Security is an open-source script that checks dozens of common best practices around deploying Docker containers in production. Based on the CIS Docker Benchmark, it audits host confi
- [[performing-ios-app-security-assessment]] *(similar)* — Performs comprehensive iOS application security assessments using Frida for dynamic instrumentation, Objection for runtime exploration, SSL pinning bypass for traffic interception, keychain extraction for credential analysis, and IPA static analysis for binary-level review. Use when conducting autho
- [[performing-security-headers-audit]] *(similar)* — Auditing HTTP security headers including CSP, HSTS, X-Frame-Options, and cookie attributes to identify missing or misconfigured browser-level protections.
- [[performing-serverless-function-security-review]] *(similar)* — Performing security reviews of serverless functions across AWS Lambda, Azure Functions, and GCP Cloud Functions to identify overly permissive execution roles, insecure environment variables, injection vulnerabilities, and missing runtime protections.

- [[performing-ssl-tls-security-assessment]] *(similar)* — Assess SSL/TLS server configurations using the sslyze Python library to evaluate cipher suites, certificate chains, protocol versions, HSTS headers, and known vulnerabilities like Heartbleed and ROBOT.
- [[rails-migration-safety]] *(similar)* — Use when planning or reviewing production database migrations, adding columns, indexes, constraints, backfills, renames, table rewrites, or concurrent operations. Covers phased rollouts, lock behavior, rollback strategy, strong_migrations compliance, and deployment ordering for schema changes.

- [[ruby]] *(similar)* — Use when writing, reviewing, or debugging pure Ruby code — idiomatic patterns, modern 3.x+ features (pattern matching, Data.define, endless methods), error handling conventions (raise vs fail, result objects), memoization, and performance idioms. For Rails use rails-guides. For testing use minitest.
- [[testing-api-security-with-owasp-top-10]] *(similar)* — Systematically assessing REST and GraphQL API endpoints against the OWASP API Security Top 10 risks using automated and manual testing techniques.
- [[testing-mobile-api-authentication]] *(similar)* — Tests authentication and authorization mechanisms in mobile application APIs to identify broken authentication, insecure token management, session fixation, privilege escalation, and IDOR vulnerabilities. Use when performing API security assessments against mobile app backends, testing JWT implement

## See Also

- [[accessibility]] — packages
- [[adev-writing-guide]] — packages
- [[agents-sdk]] — packages
- [[android-architecture-clean]] — packages
- [[android-compose-foundations]] — packages
- [[android-coroutines-flow]] — packages
- [[android-di-hilt]] — packages
- [[android-gradle-build-logic]] — packages
- [[android-kotlin-core]] — packages
- [[android-networking-retrofit-okhttp]] — packages
