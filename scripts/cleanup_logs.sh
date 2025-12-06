#!/bin/bash
# Log Rotation Script - Clean old pipeline logs

# Keep only last 7 days of logs
find /var/log/quanttrade/ -name "*.log" -type f -mtime +7 -delete

# Keep only last 5 temp pipeline logs
cd /tmp
ls -t pipeline_*.log 2>/dev/null | tail -n +6 | xargs -r rm

echo "Log cleanup completed on $(date)"
