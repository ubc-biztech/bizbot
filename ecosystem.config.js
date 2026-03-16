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

export const apps = [
    {
        name: 'bizbot',
        script: './start-bizbot.sh',
        interpreter: 'bash',
        cwd: '/opt/bizbot', // Update this to your actual deployment path
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
        min_uptime: '10s',
        // Process cleanup settings - aggressive to prevent zombie processes
        kill_timeout: 3000, // Wait only 3 seconds before force killing
        wait_ready: false, // Don't wait for ready signal
        listen_timeout: 8000, // Timeout for app to bind to port

        // Force single instance
        exec_mode: 'fork',
        // Shutdown settings
        shutdown_with_message: false,
        // Force kill any lingering processes
        force: true,
        // Disable auto-restart during shutdown
        autorestart: true,
        // Use SIGKILL instead of SIGTERM for more aggressive killing
        kill_retry_time: 100
    }
];
