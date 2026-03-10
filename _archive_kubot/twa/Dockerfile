FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy source code
COPY . .

# Create next.js build (optional, for production)
# RUN npm run build

EXPOSE 3000

# Use development server with hot reload
CMD ["npm", "run", "dev"]