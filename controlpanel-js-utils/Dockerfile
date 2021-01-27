FROM node:lts
RUN apt-get update
RUN apt-get install libsass0
RUN mkdir -p ~/.npm-global/bin
RUN npm config set prefix '~/.npm-global'
ENV PATH "~/.npm-global/bin:/root/node_modules/node-sass/bin:$PATH"
RUN mkdir -p /root/controlpanel
VOLUME ["/root/controlpanel"]
WORKDIR /root/
RUN npm install @ministryofjustice/frontend@^0.0.17-alpha
RUN npm install accessible-autocomplete@^1.6.2
RUN npm install core-js@^2.6.9
RUN npm install govuk-frontend@^3.0.0
RUN npm install html5shiv@^3.7.3
RUN npm install jquery@^3.5.0
RUN npm install node-sass@^4.13.1
RUN npm install @babel/cli@^7.5.0
RUN npm install @babel/core@^7.5.4
RUN npm install @babel/preset-env@^7.5.4
RUN npm install @testing-library/jest-dom@^4.1.0
RUN npm install babel-jest@^24.9.0
RUN npm install jest@^24.9.0
RUN npm install jsdom-simulant@^1.1.2
RUN npm install npm-run@^4.1
