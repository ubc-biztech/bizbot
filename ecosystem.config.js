/**
 * PM2 Ecosystem Configuration for BizBot
 * 
 * Usage:
 *   pm2 start ecosystem.config.js
 *   pm2 logs bizbot
 *   pm2 restart bizbot
 *   pm2 stop bizbot
 *   pm2 startup  # Enable auto-start on system boot
 *   pm2 save     # Save current process list
 */

module.exports = {
  apps: [
    {
      name: 'bizbot',
      script: 'uv',
      args: 'run python main.py',
      cwd: '/opt/bizbot',  // Update this to your actual deployment path
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        NODE_ENV: 'production'
      },
      error_file: './logs/pm2-error.log',
      out_file: './logs/pm2-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
      // Restart delay
      restart_delay: 4000,
      // Exponential backoff restart delay
      exp_backoff_restart_delay: 100,
      // Maximum number of restarts within a minute before stopping
      max_restarts: 10,
      min_uptime: '10s'
    }
  ]
};
