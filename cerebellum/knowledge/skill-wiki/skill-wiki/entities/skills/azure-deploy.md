---
title: azure-deploy
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [packages]
category: packages
related: [cloudflare-deploy]
confidence: medium
---

Execute Azure deployments for ALREADY-PREPARED applications that have existing .azure/deployment-plan.md and infrastructure files. DO NOT use this skill when the user asks to CREATE a new application — use azure-prepare instead. This skill runs azd up, azd deploy, terraform apply, and az deployment

## Metadata

- **ID:** `azure-deploy`
- **Source:** `autoskills/packages/autoskills/skills-registry/azure-deploy/SKILL.md`
- **Score:** 56.0
- **Edges:** 1

## Related Skills

- [[cloudflare-deploy]] *(similar)* — Deploy applications and infrastructure to Cloudflare using Workers, Pages, and related platform services. Use when the user asks to deploy, host, publish, or set up a project on Cloudflare.

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
