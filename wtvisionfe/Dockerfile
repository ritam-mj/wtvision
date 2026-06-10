# ==========================================
# Dockerfile for Next.js React Frontend
# ==========================================

FROM node:20-alpine

WORKDIR /app

# Copy dependency configurations
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy frontend codebase
COPY . .

EXPOSE 3000

ENV PORT 3000
ENV HOSTNAME "0.0.0.0"

# Run development server
CMD ["npm", "run", "dev"]
