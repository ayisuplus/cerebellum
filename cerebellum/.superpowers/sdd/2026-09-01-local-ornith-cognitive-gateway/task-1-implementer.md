# Task 1 implementer report

## 改动摘要

- 新增 `LocalModelConfig`，包含 endpoint、模型名、artifact SHA-256、runtime、runtime version 和 enforcement 标志。
- 新增 `load_local_model_config()`：默认禁用；启用时要求完整 pin，且只接受字面量 loopback HTTP 根路径或 `/v1`，校验 SHA-256。
- 将 `local_model: Option<LocalModelConfig>` 加入 `AppConfig` 并在加载时初始化。
- 为 API 测试中的三个 `AppConfig` 字面量补充 `local_model: None`。

## RED

命令：`cargo test -p cerebellum-app config::tests::local_model -- --nocapture`

结果：按预期失败（退出码 1），编译器报告 5 处 `cannot find function load_local_model_config`；失败原因是待实现的配置加载器不存在。

## GREEN / 回归

- `cargo test -p cerebellum-app config::tests::local_model -- --nocapture`：2 passed。
- `cargo test -p cerebellum-app config::tests -- --nocapture`：21 passed。
- `git diff --check -- crates/cerebellum-app/src/config.rs crates/cerebellum-app/src/api.rs`：通过，无 whitespace errors。

## 修改文件

- `crates/cerebellum-app/src/config.rs`
- `crates/cerebellum-app/src/api.rs`
- 本报告文件

## 剩余风险

- 两个源文件在任务开始前已有大量用户修改；本任务未重置、暂存或提交，也未触碰其余变更。
- 未启动应用或调度器；后续任务负责消费 `AppConfig.local_model`。

## 独立审查修复

- RED：将 `http://127.0.0.2:1234/v1` 加入拒绝用例后，定向测试按预期失败，报告 `accepted http://127.0.0.2:1234/v1`。
- GREEN：IPv4 loopback 判断改为 `address == std::net::Ipv4Addr::LOCALHOST`；IPv6 仍接受 loopback（`::1` 用例保持通过）。
- 修复后 `cargo test -p cerebellum-app config::tests::local_model -- --nocapture`：2 passed。
- 修复后 `cargo test -p cerebellum-app config::tests -- --nocapture`：21 passed。
- 修复后 `git diff --check -- crates/cerebellum-app/src/config.rs crates/cerebellum-app/src/api.rs`：通过。
