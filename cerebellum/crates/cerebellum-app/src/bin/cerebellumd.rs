use anyhow::Result;
use cerebellum_app::AppConfig;
use cerebellum_app::api::{AppState, serve};
use clap::Parser;
use std::net::SocketAddr;
use std::path::PathBuf;
use tracing_subscriber::EnvFilter;

#[derive(Debug, Parser)]
#[command(version, about = "Cerebellum local workflow gate sidecar")]
struct Args {
    #[arg(long, env = "CEREBELLUM_DATA_DIR", default_value = ".cerebellum")]
    data_dir: PathBuf,
    #[arg(long, env = "CEREBELLUM_BIND", default_value = "127.0.0.1:3927")]
    bind: SocketAddr,
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("cerebellum=info")),
        )
        .init();
    let args = Args::parse();
    let config = AppConfig::load(args.data_dir, args.bind)?;
    let state = AppState::new(config)?;
    serve(state).await
}
