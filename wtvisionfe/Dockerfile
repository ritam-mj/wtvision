FROM node:20-alpine

WORKDIR /app

# Copy dependency configs
COPY package*.json ./

# Install npm dependencies
RUN npm install

# Copy frontend codebase
COPY . .

EXPOSE 3000

ENV PORT 3000
ENV HOSTNAME "0.0.0.0"

# Run next dev for dynamic reload or Next.js dev server
CMD ["npm", "run", "dev"]
