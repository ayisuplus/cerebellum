# Third-party notice

This worker uses Microsoft SkillOpt, pinned to commit
`3c8873f016397817dcd40c3e5436d92fe19372b8`, under the MIT License.
The upstream source, exact commit, archive hash computed during image build,
and local registration patch are written to every optimization run manifest.

Source: https://github.com/microsoft/SkillOpt

The registration patch only exposes `CerebellumVerifyAdapter` through
SkillOpt's documented lazy environment registries. Cerebellum does not modify
SkillOpt's optimizer, gate, or model backend implementations.
