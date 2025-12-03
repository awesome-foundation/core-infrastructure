# NOTE(luka): Copied from https://github.com/haproxytech/haproxy-docker-alpine/blob/main/3.0/docker-entrypoint.sh
# 	no changes other than the annotated block near the bottom
set -e

# first arg is `-f` or `--some-option`
if [ "${1#-}" != "$1" ]; then
	set -- haproxy "$@"
fi

if [ "$1" = 'haproxy' ]; then
	shift # "haproxy"
	# if the user wants "haproxy", let's add a couple useful flags
	#   -W  -- "master-worker mode" (similar to the old "haproxy-systemd-wrapper"; allows for reload via "SIGUSR2")
	#   -db -- disables background mode
	set -- haproxy -W -db "$@"
fi

# NOTE(luka): Added templating, the rest of the entrypoint is stock
p2 -t /usr/local/etc/haproxy/haproxy.cfg.j2 > /usr/local/etc/haproxy/haproxy.cfg
# cat /usr/local/etc/haproxy/haproxy.cfg # for debugging

echo "Running haproxy $VERSION ($REVISION) $BUILDTIME" # NOTE(luka): Useful in logs to see which version is running

exec "$@"
