# The Mini App is a no-build ES-module app, so there is nothing to bundle: nginx serves
# the sources directly. VITE_API_URL is injected into a small runtime config file so the
# same image can point at different backends.
FROM nginx:1.27-alpine

ARG VITE_API_URL=http://localhost:8000/api/v1

WORKDIR /usr/share/nginx/html

COPY index.html ./
COPY src ./src

RUN printf 'window.REMARKA_API_URL = "%s";\n' "$VITE_API_URL" > ./config.js \
    && sed -i 's#<script type="module" src="./src/app.js"></script>#<script src="./config.js"></script>\n  <script type="module" src="./src/app.js"></script>#' index.html

COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
