#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST=${REMOTE_HOST:-giro-k8s}
REMOTE_DIR=${REMOTE_DIR:-/home/k8s/evtol-index-deploy}
LOCAL_ROOT=${LOCAL_ROOT:-/home/hermes/Shmape/shmape-evtol-index}
IMAGE_REF=${IMAGE_REF:-localhost/shmape-evtol-index:latest}
IMAGE_TAR=$(mktemp /tmp/evtol-index-image-XXXXXX.tar)
cleanup() { rm -f "$IMAGE_TAR"; }
trap cleanup EXIT

buildah bud --format docker -f "$LOCAL_ROOT/deploy/Dockerfile" -t "$IMAGE_REF" "$LOCAL_ROOT"
buildah push "$IMAGE_REF" "docker-archive:$IMAGE_TAR"
ssh "$REMOTE_HOST" "mkdir -p '$REMOTE_DIR/k8s' '$REMOTE_DIR/runtime'"
tar -C "$LOCAL_ROOT/deploy/k8s" -cf - . | ssh "$REMOTE_HOST" "tar -C '$REMOTE_DIR/k8s' -xf -"
ssh "$REMOTE_HOST" "cat > '$REMOTE_DIR/runtime/image.tar'" < "$IMAGE_TAR"

ssh "$REMOTE_HOST" "
  set -euo pipefail
  microk8s images import < '$REMOTE_DIR/runtime/image.tar'
  rm -f '$REMOTE_DIR/runtime/image.tar'
  microk8s kubectl apply -k '$REMOTE_DIR/k8s'
  microk8s kubectl -n shmape rollout restart deployment/evtol-index-web
  microk8s kubectl -n shmape rollout status deployment/evtol-index-web --timeout=300s
  microk8s kubectl -n shmape delete job evtol-index-refresh-smoke --ignore-not-found
  microk8s kubectl -n shmape create job evtol-index-refresh-smoke --from=cronjob/evtol-index-refresh
  microk8s kubectl -n shmape wait --for=condition=complete job/evtol-index-refresh-smoke --timeout=600s
"

curl -fsS "https://cloud.tomgiro.com/Shmape-Homepage/evtol-index/api/v1/health"
curl -fsS "https://cloud.tomgiro.com/Shmape-Homepage/evtol-index/api/v1/snapshot?range=1M" >/dev/null
printf '\nShmape eVTOL Index deployed and refreshed.\n'
