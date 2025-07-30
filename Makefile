# Include environment variables
-include .env.make

VERSION=$(shell git log -1 --pretty=%h)
SERVICE_NAME=henhouse

docker-build:
	docker build -t ${SERVICE_NAME} .

docker-buildx: docker-login
	docker buildx build --platform=linux/amd64 -t ${REGISTRY_URL}/${SERVICE_NAME} --push .

docker-login:
	docker login ${REGISTRY_URL} --username ${DOCKER_USERNAME}

docker-push: docker-login
	docker tag ${SERVICE_NAME} ${REGISTRY_URL}/${SERVICE_NAME}
	docker push ${REGISTRY_URL}/${SERVICE_NAME}

docker-load-remote:
	docker buildx build --platform=linux/amd64 -t henhouse:${VERSION} -o type=docker,dest=- . | gzip | ssh ${SERVER_HOST} 'docker load'

deploy: docker-buildx
	ssh -t ${SERVER_HOST} 'cd ~/repos/henhouse && git pull && docker compose pull && docker compose up -d'