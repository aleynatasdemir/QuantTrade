module.exports = {
    apps: [
        {
            name: 'quanttrade-backend',
            script: 'main.py',
            cwd: '/root/Quanttrade/backend',
            interpreter: '/root/Quanttrade/.venv/bin/python3',
            env: {
                PYTHONPATH: '/root/Quanttrade/src',
                PYTHONUNBUFFERED: '1'
            },
            error_file: '/var/log/quanttrade/backend-error.log',
            out_file: '/var/log/quanttrade/backend-out.log',
            time: true,
            autorestart: true,
            max_restarts: 10,
            min_uptime: '10s',
            watch: false,
            instances: 1,
            exec_mode: 'fork'
        },
        {
            name: 'telegram-bot',
            script: 'telegram_bot/bot_handler.py',
            cwd: '/root/Quanttrade/live-telegram',
            interpreter: '/root/Quanttrade/.venv/bin/python3',
            env: {
                PYTHONPATH: '/root/Quanttrade/src',
                PYTHONUNBUFFERED: '1'
            },
            error_file: '/var/log/quanttrade/telegram-error.log',
            out_file: '/var/log/quanttrade/telegram-out.log',
            time: true,
            autorestart: true,
            max_restarts: 10,
            min_uptime: '10s',
            watch: false,
            instances: 1,
            exec_mode: 'fork'
        },
        {
            name: 'quanttrade-frontend',
            script: 'npx',
            args: 'vite preview --host 0.0.0.0 --port 3000',
            cwd: '/root/Quanttrade/frontend',
            env: {
                NODE_ENV: 'production'
            },
            error_file: '/var/log/quanttrade/frontend-error.log',
            out_file: '/var/log/quanttrade/frontend-out.log',
            time: true,
            autorestart: true,
            max_restarts: 5,
            watch: false,
            instances: 1,
            exec_mode: 'fork'
        }
    ]
};
