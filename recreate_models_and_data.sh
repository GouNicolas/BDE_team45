
echo "Recreating all database-related files: migrations, database, fake data, and database dump."

echo "Removing all migrations."
rm -f fame/migrations/00* socialnetwork/migrations/00*
echo "Recreating migrations."
python3 manage.py makemigrations
echo "Removing existing database."
rm -f db.sqlite3
echo "Migrating database."
python3 manage.py migrate
echo "Recreating fake data."
python3 manage.py create_fake_data
echo "Recreating models and data."
python3 manage.py dumpdata > database_dump.json

echo "Done."
