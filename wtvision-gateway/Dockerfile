# ==========================================
# Dockerfile for Express API Gateway
# ==========================================

FROM node:20-alpine

WORKDIR /app

# Copy dependency configurations
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy service codebase
COPY . .

EXPOSE 80

# Run service
CMD ["node", "server.js"]
