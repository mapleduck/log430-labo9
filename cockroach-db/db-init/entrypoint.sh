#!/bin/bash

echo "Attendre que CockroachDB soit prêt..."
until cockroach sql --insecure --host=cockroach1 --execute="SELECT 1" > /dev/null 2>&1; do
  echo "CockroachDB n'est pas prêt, réessayer dans 3s..."
  sleep 3
done

echo "CockroachDB est prêt. Exécuter init.sql..."
cockroach sql --insecure --host=cockroach1 < /db-init/init.sql
echo "Le script init a été exécuté correctement."
