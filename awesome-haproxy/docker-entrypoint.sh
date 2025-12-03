#!/bin/sh
# Copyright 2025 Luka Kladarić, Chaos Guru
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
