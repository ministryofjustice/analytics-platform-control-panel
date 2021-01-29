FROM node:lts
ENV PATH "~/.npm-global/bin:/root/node_modules/node-sass/bin:$PATH"
COPY package.json /root/package.json
RUN apt-get update \
  && apt-get install libsass0 \
  && mkdir -p ~/.npm-global/bin /root/controlpanel \
  && npm config set prefix '~/.npm-global'
VOLUME ["/root/controlpanel"]
WORKDIR /root/
RUN npm install
