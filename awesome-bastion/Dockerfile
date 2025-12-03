FROM alpine:latest
RUN apk --update add openssh && rm -f /var/cache/apk/*
RUN ssh-keygen -A
RUN echo "PermitRootLogin no" >> /etc/ssh/sshd_config && \
  echo "PasswordAuthentication no" >> /etc/ssh/sshd_config && \
  echo "ChallengeResponseAuthentication no" >> /etc/ssh/sshd_config && \
  echo "Port 9022" >> /etc/ssh/sshd_config && \
  echo "StrictModes no" >> /etc/ssh/sshd_config && \
  sed -e 's/AllowTcpForwarding no/AllowTcpForwarding yes/' --in-place /etc/ssh/sshd_config

RUN cat /etc/ssh/sshd_config

RUN adduser -D dev && passwd -d dev && mkdir /home/dev/.ssh && chown dev:nogroup /home/dev/.ssh && chmod 700 /home/dev/.ssh
VOLUME /home/dev/.ssh
ADD harden.sh /usr/bin/harden.sh
# this breaks the authorized_keys rebuild script in docker-entrypoint.sh
# RUN chmod 700 /usr/bin/harden.sh && /usr/bin/harden.sh
# this is the only thing we need from the harden script
RUN chmod a+r /etc/ssh/ssh_*
USER dev
CMD ["/usr/sbin/sshd", "-D"]

COPY --chown=dev authorized_users /home/dev/
COPY --chown=dev docker-entrypoint.sh /
COPY --chown=dev ssh.config /home/dev/.ssh/config

EXPOSE 9022

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["/usr/sbin/sshd", "-De", "-o LogLevel=Verbose"]
