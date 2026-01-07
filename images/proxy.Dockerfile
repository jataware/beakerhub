FROM node:22
RUN npm install --global configurable-http-proxy
USER proxy:proxy
CMD ["configurable-http-proxy", \
  "--ip", "0.0.0.0", \
  "--port", "8000", \
  "--api-ip", "0.0.0.0", \
  "--api-port", "8001", \
  "--default-target", "http://beakerhub:8888", \
  "--no-prepend-path", "--no-include-prefix", \
  "--auto-rewrite", "--change-origin", "--insecure" \
]
