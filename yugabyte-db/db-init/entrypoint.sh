#!/bin/bash

echo "Démarrer yugabyted..."
/home/yugabyte/bin/yugabyted start --daemon=true

echo "En train d'attendre YSQL..."
until /home/yugabyte/bin/ysqlsh -h yugabyte1 -U yugabyte -c "SELECT 1" > /dev/null 2>&1; do
  echo "YSQL n'est pas connecté, réessayer dans 3s..."
  sleep 3
done

echo "YSQL est prêt. Exécuter init.sql..."
/home/yugabyte/bin/ysqlsh -h yugabyte1 -U yugabyte -d yugabyte -f /db-init/init.sql
echo "Le script init a été exécuté correctement."

