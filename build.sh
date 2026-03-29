#!/usr/bin/env bash
set -e

IMAGE="nasir17/week5ver-bot"
SHA=$(git rev-parse --short HEAD)

echo "Building $IMAGE:$SHA and $IMAGE:latest ..."
docker build -t "$IMAGE:$SHA" -t "$IMAGE:latest" .

echo "Pushing ..."
docker push "$IMAGE:$SHA"
docker push "$IMAGE:latest"

echo "Done: $IMAGE:$SHA / $IMAGE:latest"
