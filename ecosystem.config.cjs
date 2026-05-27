const port = String(process.env.PORT || 4173);
const host = process.env.HOST || "0.0.0.0";
const staticDir = process.env.STATIC_DIR || "docs/.vitepress/dist";

module.exports = {
  apps: [
    {
      name: "learning-portal",
      script: "./server.mjs",
      cwd: __dirname,
      exec_mode: "fork",
      instances: 1,
      watch: false,
      autorestart: true,
      max_memory_restart: "256M",
      out_file: "./logs/pm2-out.log",
      error_file: "./logs/pm2-error.log",
      merge_logs: true,
      env: {
        NODE_ENV: "production",
        HOST: host,
        PORT: port,
        STATIC_DIR: staticDir,
      },
      env_production: {
        NODE_ENV: "production",
        HOST: host,
        PORT: port,
        STATIC_DIR: staticDir,
      },
    },
  ],
};
