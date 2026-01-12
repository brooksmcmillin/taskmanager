#!/bin/bash
# Copy to /etc/letsencrypt/renewal-hooks/deploy/postgres-ssl.sh
cp /etc/letsencrypt/live/todo.brooksmcmillin.com/fullchain.pem /home/brooks/build/taskmanager/services/db/certs/server.crt
cp /etc/letsencrypt/live/todo.brooksmcmillin.com/privkey.pem /home/brooks/build/taskmanager/services/db/certs/server.key
chown 999:999 /home/brooks/build/taskmanager/services/db/certs/*
chmod 600 /home/brooks/build/taskmanager/services/db/certs/server.key
docker exec postgres_db psql -U taskmanager -c "SELECT pg_reload_conf();"
