# ==========================================
# Dockerfile for Rentals Backend Service
# ==========================================

FROM node:20-alpine

# Install openssl for prisma engine compatibility on Alpine
RUN apk add --no-cache openssl

WORKDIR /app

# Copy dependency configurations
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy prisma schema to generate client
COPY prisma ./prisma/

# Generate prisma client inside container
RUN npx prisma generate

# Copy service codebase
COPY . .

EXPOSE 5000

ENV PORT 5000

# Run development server
CMD ["npm", "run", "dev"]
