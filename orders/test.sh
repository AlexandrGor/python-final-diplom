#не забудь pip install -r requirements.txt

. .env-test.sh
docker-compose -f docker-compose-test.yml up -d
pytest
docker-compose -f docker-compose-test.yml down
