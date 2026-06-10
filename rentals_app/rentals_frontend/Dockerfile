# ==========================================
# Dockerfile for Rentals Frontend Service
# ==========================================

FROM node:20-alpine

WORKDIR /app

# Copy dependency configurations
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy frontend codebase
COPY . .

EXPOSE 3001

ENV PORT 3001
ENV HOSTNAME "0.0.0.0"

# Run development server
CMD ["npm", "run", "dev"]
