FROM node:20-alpine

WORKDIR /app

# Install dependencies (as root for correct permissions)
COPY package.json package-lock.json* ./
RUN npm install

# Copy source — node user owns everything
COPY --chown=node:node . .

# Vite needs write access to /app for .timestamp temp files.
# Grant write permission on the app directory before switching user.
RUN chmod -R 777 /app

USER node

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
