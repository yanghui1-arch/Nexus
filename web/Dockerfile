FROM node:24-bookworm-slim AS build

WORKDIR /app

COPY package.json skills-lock.json ./
RUN npm install

COPY . .
RUN npm run build

FROM nginx:1.29-bookworm

COPY docker/nginx-web.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
