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

FROM haproxytech/haproxy-alpine:3.0

# provided by docker/metadata-action
ARG BUILDTIME=_buildtime
ENV BUILDTIME=$BUILDTIME
ARG VERSION=_version
ENV VERSION=$VERSION
ARG REVISION=_revision
ENV REVISION=$REVISION

ENV HAPROXY_LISTEN_PORT=8000
ENV HAPROXY_APP_NAME=haproxy
ENV HAPROXY_APP_PORT=8080
ENV HAPROXY_APP_HOST=127.0.0.1
ENV HAPROXY_TIMEOUT_SERVER=1m

ENV P2_RELEASE=r18

# Install p2, the j2cli reimplementation in Go which allows us to template the config file
ADD https://github.com/wrouesnel/p2cli/releases/download/$P2_RELEASE/p2cli_${P2_RELEASE}_linux-amd64.tar.gz /tmp/p2cli.tar.gz
RUN tar -C /tmp -xzf /tmp/p2cli.tar.gz
RUN mv /tmp/p2cli_${P2_RELEASE}_linux-amd64/p2 /bin/p2
RUN chmod u+x /bin/p2

# Our forked docker-entrypoint, which does the templating at runtime
COPY docker-entrypoint.sh /
COPY haproxy.cfg.j2 /usr/local/etc/haproxy/haproxy.cfg.j2

# Check config file
RUN p2 -t /usr/local/etc/haproxy/haproxy.cfg.j2 > /usr/local/etc/haproxy/haproxy.cfg
RUN haproxy -c -f /usr/local/etc/haproxy/haproxy.cfg

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["haproxy", "-f", "/usr/local/etc/haproxy/haproxy.cfg"]
