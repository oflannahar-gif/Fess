#!/bin/bash
# Backup otomatis ke GitHub
# Log disimpan di /home/aether/fess/backup_log.txt

cd /home/aether/fess || exit
echo "===== $(date '+%Y-%m-%d %H:%M:%S') Mulai backup =====" >> backup_log.txt

# pastikan PATH
export PATH=/usr/bin:/bin:/usr/local/bin

# Tambahkan SEMUA perubahan (fix utama)
/usr/bin/git add -A >> backup_log.txt 2>&1

# Commit perubahan
/usr/bin/git commit -m "Auto backup $(date '+%Y-%m-%d %H:%M:%S')" >> backup_log.txt 2>&1

# Push ke GitHub
/usr/bin/git push origin main >> backup_log.txt 2>&1

echo "===== $(date '+%Y-%m-%d %H:%M:%S') Selesai backup =====" >> backup_log.txt
